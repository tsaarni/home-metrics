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
        self.rates = config["rates"]

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
        response.raise_for_status()

        res = response.json()

        metrics = prometheus.Metrics()
        samples = metrics.gauge(
            "electric_price_eur",
            "Electricity price (euros per kWh)",
        )

        for item in res:
            item_time = datetime.fromisoformat(item["DateTime"]).timestamp() * 1000

            samples.add(item["PriceNoTax"], labels={"tax": "false"}, timestamp_msec=item_time)
            samples.add(item["PriceWithTax"], labels={"tax": "true"}, timestamp_msec=item_time)

        # Generate day/night transmission rates for the next 24 hours.
        # The day rate begins at 07:00 and ends at 21:59.
        # The night rate begins at 22:00 and ends at 06:59.
        transmission = metrics.gauge(
            "electric_transmission_price_eur",
            "Electricity transmission price (euros per kWh)",
        )

        # Generate electricity tax rates.
        tax = metrics.gauge(
            "electric_tax_eur",
            "Electricity tax (euros per kWh)",
        )

        current_time = datetime.now()
        for i in range(24):
            t = current_time + utils.parse_timedelta(f"{i}h")
            t = t.replace(minute=0, second=0, microsecond=0)
            if 7 <= t.hour <= 21:
                transmission.add(self.rates["day"], labels={"rate": "day"}, timestamp_msec=t.timestamp() * 1000)
            else:
                transmission.add(self.rates["night"], labels={"rate": "night"}, timestamp_msec=t.timestamp() * 1000)

            tax.add(self.rates["tax"], timestamp_msec=t.timestamp() * 1000)

        logger.info(f"Storing metrics: url={self.database_url}")
        await client.post(self.database_url, content=metrics.format())


task.register(SpotHinta, "spot-hinta")
