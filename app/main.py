#!/bin/env python3

import argparse
import asyncio
import logging.config
import sys

import task
import yaml

# Configure logger.
with open("logging.yaml") as f:
    config = yaml.safe_load(f)
    logging.config.dictConfig(config)

logger = logging.getLogger("app.main")

# Dummy import to make sure all task classes are registered.
import spothinta, skoda, goecharger, shelly1, shelly2, zwave, zigbee, melcloud


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

        # Instantiate task classes that are requested in the configuration file.
        self.tasks = []
        for s in config["sensors"]:
            # Combine global config with task-specific config.
            task_config = s["config"]
            if "global" in config:
                task_config.update(config["global"])

            # Instantiate task class and configure it.
            cls = task.get_task_class(s["type"])
            instance = cls()
            instance.configure(s.get("name", ""), task_config)

            self.tasks.append(instance)

    async def start(self):
        # Start all tasks.
        for s in self.tasks:
            logger.info(f"Starting task: {s}")
            asyncio.create_task(s.start())

        # Do not exit, keep running until killed.
        await asyncio.Event().wait()


async def main(args):
    await Application(args).start()


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1:]))
