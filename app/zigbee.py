import logging

import aiomqtt
import sensor

logger = logging.getLogger("zigbee")


class Zigbee(object):
    def configure(self, instance_name, config):
        self.instance_name = instance_name
        self.server = config["server"]
        self.topic = config["topic"]
        self.database_url = config["database_url"]

    async def start(self):
        logger.info(f"Starting Zigbee instance_name={self.instance_name} server={self.server} topic={self.topic}")

        async with aiomqtt.Client(self.server) as client:
            async with client.messages() as messages:
                await client.subscribe(self.topic)
                async for message in messages:
                    logger.debug(message.payload)


sensor.register(Zigbee, "zigbee")
