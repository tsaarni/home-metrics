import asyncio
import json
import logging

import aiomqtt
import httpx
import prometheus
import task

logger = logging.getLogger("app.zigbee")


class Zigbee(object):
    def configure(self, instance_name, config):
        self.instance_name = instance_name
        self.server = config["server"]
        self.port = config.get("port", 1883)
        self.topic = config["topic"]
        self.database_url = config["database_url"]

    async def start(self):
        logger.info(f"Starting Zigbee instance_name={self.instance_name} server={self.server} topic={self.topic}")
        while True:
            await self.loop_forever()

    async def loop_forever(self):
        async with aiomqtt.Client(self.server, self.port) as client:
            await client.subscribe(self.topic)
            async for message in client.messages:
                # logger.debug(f"Received message: {message.topic} {message.payload}")

                # Skip (informational) bridge messages.
                if message.topic.matches("zigbee2mqtt/bridge/#"):
                    continue
                try:
                    # ensure that payload is string
                    payload = (
                        message.payload.decode("utf-8") if isinstance(message.payload, bytes) else str(message.payload)
                    )
                    event = json.loads(payload)
                    topic = str(message.topic).split("/")
                    await self.sensor_event(topic[1], event)
                except json.JSONDecodeError:
                    logger.debug(f"Received non-JSON message: {message.payload}")

    async def sensor_event(self, sensor_name, event):
        logger.debug(f"{sensor_name} {event}")

        # zigbee attribute name to prometheus metric name mapping
        mapping = {
            "temperature": "temperature_celsius",
            "battery": "battery_percentage",
            "humidity": "humidity_percentage",
            "pressure": "pressure_hpa",
            "occupancy": "occupancy_boolean",
            "contact": "contact_boolean",
            "illuminance_lux": "illuminance_lux",
            "linkquality": "linkquality_dbm",
            "consumption": "electric_consumption_kwh",
            "power": "electric_power_w",
            # "voltage": "electric_voltage_v",  # should be divided by 1000 to convert to volts
        }

        metrics = prometheus.Metrics()
        for k, v in event.items():
            if k in mapping:
                samples = metrics.gauge(mapping[k], "")
                samples.add(v, labels={"sensor": sensor_name})

        client = httpx.AsyncClient()
        await client.post(self.database_url, content=metrics.format())


task.register(Zigbee, "zigbee")
