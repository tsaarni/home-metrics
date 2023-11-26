import datetime
import json
import logging
import re

import aiomqtt
import httpx
import prometheus
import task

logger = logging.getLogger("app.zwave")


class Zwave(object):
    def configure(self, instance_name, config):
        self.instance_name = instance_name
        self.server = config["server"]
        self.port = config.get("port", 1883)
        self.topic = config["topic"]
        self.database_url = config["database_url"]

    async def start(self):
        logger.info(f"Starting Z-Wave instance_name={self.instance_name} server={self.server} topic={self.topic}")
        while True:
            try:
                await self.loop_forever()
            except Exception as e:
                logger.exception("Error:", exc_info=e)

    async def loop_forever(self):
        async with aiomqtt.Client(self.server, self.port) as client:
            async with client.messages() as messages:
                await client.subscribe(self.topic)
                async for message in messages:
                    # logger.debug(f"Received message: {message.topic} {message.payload}")

                    # Skip informational messages.
                    if message.topic.matches("zwave/_CLIENTS/#"):
                        continue
                    if message.topic.matches("zwave/+/lastActive"):
                        continue
                    if message.topic.matches("zwave/+/status"):
                        continue

                    # Parse the topic: <nodeId>/<commandClass>/<endpoint>/<property>/<propertyKey?>
                    parts = str(message.topic).split("/")

                    await self.sensor_event(
                        parts[1],  # node_id
                        int(parts[2]),  # command_class
                        int(parts[3]),  # endpoint
                        parts[4],  # property
                        parts[5] if len(parts) > 5 else None,  # property_key
                        json.loads(message.payload),
                    )

    async def sensor_event(
        self, node_id: str, command_class: int, endpoint: int, property: str, property_key: str | None, payload: dict
    ):
        # Skip command classes we don't care about, out of the following we will receive:
        #   - Basic: 32
        #   - SensorBinary: 48
        #   - SensorMultilevel: 49
        #   - Meter: 50
        #   - Thermostat Mode: 64
        #   - Thermostat SetPoint: 67
        #   - Configuration: 112
        #   - ManufacturerSpecific: 114
        #   - Battery: 128
        #   - Version: 134
        if command_class not in [48, 49, 50, 128]:
            return

        payload_dbg = {
            "time": datetime.datetime.fromtimestamp(payload["time"] / 1000).isoformat(),
            "value": payload["value"] if "value" in payload else None,
        }

        logger.debug(
            f"node_id={node_id} command_class={command_class} endpoint={endpoint} property={property} property_key={property_key} payload={payload_dbg}"
        )

        metrics = prometheus.Metrics()

        # Check the Z-Wave JS UI to find out identifiers.

        # Topic examples:
        #
        # zwave/thermostat-bedroom/49/3/Air_temperature
        # zwave/thermostat-bathroom/49/0/Air_temperature
        # zwave/door-livingroom/48/0/Door-Window
        # zwave/door-livingroom/49/0/Illuminance
        # zwave/door-livingroom/49/0/Air_temperature
        # zwave/thermostat-toilet/50/4/value/66049
        # zwave/thermostat-toilet/50/4/value/66561
        # zwave/thermostat-hall/50/4/value/65537
        #

        # Temperature
        #  - endpoint 0 in old thermostats
        #  - endpoint 3 in new thermostats
        #  - door sensor
        if command_class == 49 and (endpoint == 0 or endpoint == 3):
            if property != "Air_temperature":
                return

            metrics.gauge("temperature_celsius", labels={"sensor": node_id}).add(
                payload["value"], timestamp_msec=payload["time"]
            )

        if command_class == 50 and endpoint == 4 and property == "value":
            if property_key == "65537":
                # Electric consumption kWh
                metrics.gauge("electric_consumption_kwh", labels={"sensor": node_id}).add(
                    payload["value"], timestamp_msec=payload["time"]
                )
            elif property_key == "66049":
                # Electric power W
                metrics.gauge("electric_power_w", labels={"sensor": node_id}).add(
                    payload["value"], timestamp_msec=payload["time"]
                )
            elif property_key == "66561":
                # Electric voltage V
                metrics.gauge("electric_voltage_v", labels={"sensor": node_id}).add(
                    payload["value"], timestamp_msec=payload["time"]
                )

        # Door contact
        if command_class == 48 and endpoint == 0 and node_id != "siren-kitchen":
            # in zwave true means open, false means closed
            # turn the logic other way around to signify
            # "contact"  true == closed, false == open
            metrics.gauge("contact_boolean", labels={"sensor": node_id}).add(
                not payload["value"], timestamp_msec=payload["time"]
            )

        # Battery
        if command_class == 128 and endpoint == 0 and property == "level":
            metrics.gauge("battery_percentage", labels={"sensor": node_id}).add(
                payload["value"], timestamp_msec=payload["time"]
            )

        # If we have collected any metrics, store them.
        if metrics.num_samples() > 0:
            client = httpx.AsyncClient()
            await client.post(self.database_url, content=metrics.format())


task.register(Zwave, "zwave")
