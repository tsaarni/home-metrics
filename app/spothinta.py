import asyncio
import logging
from datetime import datetime

import httpx
import prometheus
import task

SPOT_HINTA_URI = "https://api.spot-hinta.fi/TodayAndDayForward"

logger = logging.getLogger("app.spot-hinta")


class SpotHinta(object):
    def configure(self, instance_name, config):
        self.instance_name = instance_name
        self.poll_period_sec = config.get("poll-period-sec", 3600)
        self.database_url = config["database_url"]

    async def start(self):
        logger.info(f"Starting SpotHinta instance_name={self.instance_name} poll_period_sec={self.poll_period_sec}")

        while True:
            try:
                await self.update_metrics()
            except Exception as e:
                logger.exception("Error:", exc_info=e)
                await asyncio.sleep(60)

            logger.info(f"Sleeping for {self.poll_period_sec} seconds")
            await asyncio.sleep(self.poll_period_sec)

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
