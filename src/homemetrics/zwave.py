import asyncio
import datetime
import json
import logging
import re

import aiomqtt
import httpx
import prometheus
import task

from dataclasses import dataclass

logger = logging.getLogger("app.zwave")


@dataclass
class SensorData:
    sensor: str
    property: str
    value: float
    time: int


class Zwave(object):
    def configure(self, instance_name, config):
        self.instance_name = instance_name
        self.server = config["server"]
        self.port = config.get("port", 1883)
        self.topic = config["topic"]
        self.database_url = config["database_url"]

    async def start(self):
        logger.info(f"Starting Z-Wave instance_name={self.instance_name} server={self.server} topic={self.topic}")

        async with aiomqtt.Client(self.server, self.port) as client:
            await client.subscribe(self.topic)
            async for message in client.messages:
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

                # ensure that payload is string
                payload = (
                    message.payload.decode("utf-8") if isinstance(message.payload, bytes) else str(message.payload)
                )

                data = self.parse_event(
                    parts[1],  # node_id
                    int(parts[2]),  # command_class
                    int(parts[3]),  # endpoint
                    parts[4],  # property
                    parts[5] if len(parts) > 5 else None,  # property_key
                    json.loads(payload),
                )

                if data:
                    # Store the data in the database.
                    metrics = prometheus.Metrics()
                    metrics.gauge(data.property, labels={"sensor": data.sensor}).add(
                        data.value, timestamp_msec=data.time
                    )
                    await httpx.AsyncClient().post(self.database_url, content=metrics.format())

                    # Publish the data to the MQTT broker.
                    await client.publish(f"home/{data.sensor}/{data.property}", data.value)

    def parse_event(
        self, node_id: str, command_class: int, endpoint: int, property: str, property_key: str | None, payload: dict
    ) -> SensorData | None:
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
            return None

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
                return None
            return SensorData(
                sensor=node_id, property="temperature_celsius", value=payload["value"], time=payload["time"]
            )

        if command_class == 50 and endpoint == 4 and property == "value":
            if property_key == "65537":
                # Electric consumption kWh
                return SensorData(
                    sensor=node_id, property="electric_consumption_kwh", value=payload["value"], time=payload["time"]
                )
            elif property_key == "66049":
                # Electric power W
                return SensorData(
                    sensor=node_id, property="electric_power_w", value=payload["value"], time=payload["time"]
                )
            elif property_key == "66561":
                # Electric voltage V
                return SensorData(
                    sensor=node_id, property="electric_voltage_v", value=payload["value"], time=payload["time"]
                )

        # Door contact
        if command_class == 48 and endpoint == 0 and node_id != "siren-kitchen":
            # in zwave true means open, false means closed
            # turn the logic other way around to signify
            # "contact"  true == closed, false == open
            return SensorData(
                sensor=node_id, property="contact_boolean", value=not payload["value"], time=payload["time"]
            )

        # Battery
        if command_class == 128 and endpoint == 0 and property == "level":
            return SensorData(
                sensor=node_id, property="battery_percentage", value=payload["value"], time=payload["time"]
            )

        return None


task.register(Zwave, "zwave")
