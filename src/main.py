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
import homemetrics


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
            # Closure to wrap task in try/except block and retry on failure.
            async def task_wrapper(s):
                logger.info(f"Starting task: {s}")
                delay = 10
                last_exception_time = asyncio.get_event_loop.time()
                while True:
                    try:
                        await s.start()
                    except Exception as e:
                        # Reset retry delay to 10 seconds if no exceptions in the last 60 minutes.
                        current_time = asyncio.get_event_loop().time()
                        if current_time - last_exception_time > 60 * 60:
                            delay = 10
                        last_exception_time = current_time
                        logger.exception(f"Error in task {s}, retry will be in {delay} seconds:", exc_info=e)
                        await asyncio.sleep(delay)
                        logger.info(f"Retrying task {s} after {delay} seconds")
                        delay *= 2  # Exponential backoff.
                        delay = min(delay, 60 * 60)  # Limit to 60 minutes.

            asyncio.create_task(task_wrapper(s))

        # Do not exit, keep running until killed.
        await asyncio.Event().wait()


async def main(args):
    await Application(args).start()


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1:]))
