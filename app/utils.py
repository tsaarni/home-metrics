import asyncio
import datetime
import logging
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
