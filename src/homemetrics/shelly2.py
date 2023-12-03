import asyncio
import logging

import httpx
import prometheus
import task
import utils

logger = logging.getLogger("app.shelly2")


class Shelly2(object):
    def configure(self, instance_name, config):
        self.instance_name = instance_name
        self.url = config["url"]
        self.poll_period = utils.parse_timedelta(config.get("poll-period", "1m"))
        self.database_url = config["database_url"]

    async def start(self):
        logger.info(
            f"Starting Shelly 2nd Gen instance_name={self.instance_name} url={self.url} poll_period_sec={self.poll_period}"
        )

        while True:
            try:
                await self.update_metrics()
            except Exception as e:
                logger.exception("Error:", exc_info=e)
                await asyncio.sleep(60)

            logger.info(f"Sleeping for {self.poll_period}")
            await asyncio.sleep(self.poll_period.total_seconds())

    async def update_metrics(self):
        logger.debug(f"Fetching data: url={self.url}")

        client = httpx.AsyncClient()
        response = await client.post(self.url, json={"id": 1, "method": "Shelly.GetStatus"})

        if response.status_code == 200:
            res = response.json()

            metrics = prometheus.Metrics()

            samples = metrics.gauge("electric_power_w", "Instantaneous power in Watt.")
            samples.add(res["result"]["switch:0"]["apower"], labels={"sensor": self.instance_name, "phase": "all"})

            samples = metrics.counter("electric_consumption_kwh", "Total consumed energy in kWh.")
            samples.add(
                res["result"]["switch:0"]["aenergy"]["total"] / 1000,
                labels={"sensor": self.instance_name, "phase": "all"},
            )

            samples = metrics.gauge("electric_current_a", "Current in Amps")
            samples.add(res["result"]["switch:0"]["current"], labels={"sensor": self.instance_name})

            samples = metrics.gauge("electric_voltage_v", "RMS voltage in Volts")
            samples.add(res["result"]["switch:0"]["voltage"], labels={"sensor": self.instance_name})

        else:
            raise task.TaskException(f"failed to fetch data: {response.status_code}")

        logger.info(f"Storing metrics: url={self.database_url}")
        await client.post(self.database_url, content=metrics.format())


task.register(Shelly2, "shelly2")
