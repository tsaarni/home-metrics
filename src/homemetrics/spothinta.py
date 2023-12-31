import asyncio
import logging
from datetime import datetime

import httpx
import prometheus
import task
import utils

SPOT_HINTA_URI = "https://api.spot-hinta.fi/TodayAndDayForward"

logger = logging.getLogger("app.spot-hinta")


class SpotHinta(object):
    def configure(self, instance_name, config):
        self.instance_name = instance_name
        self.poll_period = utils.parse_timedelta(config.get("poll-period", "8h"))
        self.database_url = config["database_url"]

    async def start(self):
        logger.info(f"Starting SpotHinta instance_name={self.instance_name} poll_period_sec={self.poll_period}")

        while True:
            await self.update_metrics()

            delay = utils.random_jitter(self.poll_period)
            logger.info(f"Sleeping for {delay}")
            await asyncio.sleep(delay.total_seconds())

    async def update_metrics(self):
        logger.debug(f"Fetching data: url={SPOT_HINTA_URI}")

        client = httpx.AsyncClient()
        response = await client.get(SPOT_HINTA_URI)

        if response.status_code == 200:
            res = response.json()

            metrics = prometheus.Metrics()
            samples = metrics.gauge(
                "electric_price_eur",
                "Electricity price (euros per kWh)",
                labels={"tax": "false"},
            )

            for item in res:
                item_time = datetime.fromisoformat(item["DateTime"]).timestamp() * 1000

                samples.add(item["PriceNoTax"], labels={"tax": "false"}, timestamp_msec=item_time)
                samples.add(item["PriceWithTax"], labels={"tax": "true"}, timestamp_msec=item_time)

        else:
            raise task.TaskException(f"failed to fetch data: {response.status_code}")

        logger.info(f"Storing metrics: url={self.database_url}")
        await client.post(self.database_url, content=metrics.format())


task.register(SpotHinta, "spot-hinta")
