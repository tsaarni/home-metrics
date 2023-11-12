#!/bin/env python3

import argparse
import asyncio
import logging.config
import sys

import sensor
import yaml

# Configure logger.
with open("logging.yaml") as f:
    config = yaml.safe_load(f)
    logging.config.dictConfig(config)

logger = logging.getLogger("main")

# Dummy import to make sure all sensor classes are registered.
import spothinta, skoda, goecharger, shelly1, shelly2, zwave, zigbee


class Application(object):
    def __init__(self, args):
        # Parse command line arguments.
        ap = argparse.ArgumentParser()
        ap.add_argument("--config", required=True, help="Path to config file")
        args = ap.parse_args(args)

        if not args.config:
            logger.error("No config file specified")
            exit(1)

        # Load configuration file.
        logger.info(f"Loading configuration file: {args.config}")
        config = yaml.safe_load(open(args.config))

        # Instantiate sensor classes that are requested in the configuration file.
        self.sensors = []
        for s in config["sensors"]:
            # Combine global config with sensor-specific config.
            sensor_config = s["config"]
            sensor_config.update(config["global"])

            # Instantiate sensor class and configure it.
            cls = sensor.get_sensor_class(s["type"])
            instance = cls()
            instance.configure(s.get("name", ""), sensor_config)

            self.sensors.append(instance)

    async def start(self):
        # Start all sensors.
        for s in self.sensors:
            logger.info(f"Starting sensor: {s}")
            asyncio.create_task(s.start())

        # Do not exit, keep running until killed.
        await asyncio.Event().wait()


async def main(args):
    await Application(args).start()


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1:]))
