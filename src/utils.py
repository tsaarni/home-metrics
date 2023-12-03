import asyncio
import datetime
import logging
import random
from typing import List

logger = logging.getLogger("app.utils")


async def wait_until(schedule: List[datetime.time]) -> datetime.time:
    """Wait until a next scheduled wakeup time.

    :param schedule: Array of times to wake up at.
    :return: The time of this wakeup.
    """

    # Sort the times in the schedule from earliest to latest.
    schedule.sort()

    now = datetime.datetime.now()

    next_wakeup = None
    for dt in schedule:
        if now.time() < dt:
            # Its before scheduled time, so schedule for today.
            next_wakeup = datetime.datetime(now.year, now.month, now.day, dt.hour, dt.minute, dt.second)
            break

    if next_wakeup is None:
        # It was past all scheduled times, so schedule for earliest time tomorrow.
        next_wakeup = datetime.datetime.combine(now.date() + datetime.timedelta(days=1), schedule[0])

    seconds_until_wakeup = (next_wakeup - now).total_seconds()
    logger.debug(f"Sleeping until {next_wakeup} ({seconds_until_wakeup} seconds)")
    await asyncio.sleep(seconds_until_wakeup)

    return next_wakeup.time()


async def retry_until_successful(func, max_retries=5):
    """Retry a function until it succeeds.

    :param func: The function to call.
    :param max_retries: Maximum number of retries.
    """
    delay = 1

    for i in range(max_retries):
        try:
            return await func()
        except Exception as e:
            logger.exception("Error:", exc_info=e)
            logger.info(f"Retrying in {delay} seconds")
            await asyncio.sleep(delay)
            delay *= 2  # Exponential backoff.
            delay = min(delay, 60 * 5)  # Limit to 5 minutes.

    raise Exception(f"Failed after {max_retries} retries")


def parse_timedelta(interval: str) -> datetime.timedelta:
    """Parse a time interval string into a timedelta.

    :param interval: The interval string. For example, "5m" for 5 minutes. Supported units are "s", "m", "h", and "d".
    :return: The timedelta.
    """
    unit = interval[-1]
    value = int(interval[:-1])
    if unit == "s":
        return datetime.timedelta(seconds=value)
    elif unit == "m":
        return datetime.timedelta(minutes=value)
    elif unit == "h":
        return datetime.timedelta(hours=value)
    elif unit == "d":
        return datetime.timedelta(days=value)
    else:
        raise ValueError(f"Invalid unit: {unit}")


def random_jitter(interval: datetime.timedelta, jitter: float = 0.1) -> datetime.timedelta:
    """Add a random jitter to a timedelta.

    :param interval: The timedelta to add jitter to.
    :param jitter: The amount of jitter to add, as a percentage of the interval.
    :return: The jittered timedelta.
    """
    return interval * (1 + (random.random() * 2 - 1) * jitter)
