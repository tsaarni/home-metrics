import json
import logging
import re

import aiomqtt
import httpx
import prometheus
import sensor

logger = logging.getLogger("zwave")


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

                    # Skip (informational) bridge messages.
                    if message.topic.matches("zwave/_CLIENTS/#"):
                        continue
                    try:
                        # Topic examples:
                        #
                        # zwave/thermostat-bedroom/49/3/Air_temperature
                        # zwave/thermostat-bathroom/49/0/Air_temperature
                        # zwave/door-livingroom/48/0/Door-Window
                        # zwave/thermostat-toilet/50/4/value/66049
                        # zwave/thermostat-toilet/50/4/value/66561
                        # zwave/thermostat-hall/50/4/value/65537
                        #
                        # Parse topic with regex
                        match = re.match(r"zwave/([\w-]+)/(\d+)/(\d+)/(.*)", str(message.topic))
                        if not match:
                            logger.error(f"Failed to parse topic: {message.topic} message={message.payload}")
                            continue

                        sensor = match.group(1)
                        command_class = int(match.group(2))
                        sensor_id = int(match.group(3))
                        rest = match.group(4)
                        event = json.loads(message.payload)

                        await self.sensor_event(sensor, command_class, sensor_id, rest, event)

                    except json.JSONDecodeError:
                        logger.debug(f"Received non-JSON message: {message.payload}")

    async def sensor_event(self, sensor, command_class, sensor_id, rest, event):
        logger.debug(f"sensor={sensor} command_class={command_class} sensor_id={sensor_id} {rest} {event}")

        metrics = prometheus.Metrics()

        # Temperature
        #  - sensorId 0 in old thermostats
        #  - sensorId 3 in new thermostats
        #  - door sensor zwave/door-livingroom/49/0/Illuminance
        #                zwave/door-livingroom/49/0/Air_temperature
        if command_class == 49 and (sensor_id == 0 or sensor_id == 3):
            logger.debug(f"Temperature: {event['value']}")
            metrics.gauge("temperature_celsius", labels={"sensor": sensor}).add(event["value"])

        # Electric consumption kWh
        if command_class == 50 and sensor_id == 4 and rest == "value/65537":
            metrics.gauge("electric_consumption_kwh", labels={"sensor": sensor}).add(event["value"])

        # Electric power W
        if command_class == 50 and sensor_id == 4 and rest == "value/66049":
            metrics.gauge("electric_power_w", labels={"sensor": sensor}).add(event["value"])

        # Electric voltage V
        if command_class == 50 and sensor_id == 4 and rest == "value/66561":
            metrics.gauge("electric_voltage_v", labels={"sensor": sensor}).add(event["value"])

        # Door contact
        if command_class == 48 and sensor_id == 0 and sensor != "siren-kitchen":
            # in zwave true means open, false means closed
            # turn the logic other way around to signify
            # "contact"  true == closed, false == open
            metrics.gauge("contact_boolean", labels={"sensor": sensor}).add(not event["value"])

        # Battery
        if command_class == 128 and sensor_id == 0 and rest == "level":
            metrics.gauge("battery_percentage", labels={"sensor": sensor}).add(event["value"])

        # If we have collected any metrics, store them.
        if metrics.num_samples() > 0:
            client = httpx.AsyncClient()
            await client.post(self.database_url, content=metrics.format())


sensor.register(Zwave, "zwave")
