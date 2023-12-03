import asyncio
import logging

import httpx
import prometheus
import task
import utils

logger = logging.getLogger("app.shelly1")


class Shelly1(object):
    def configure(self, instance_name, config):
        self.instance_name = instance_name
        self.url = config["url"]
        self.poll_period = utils.parse_timedelta(config.get("poll-period", "5s"))
        self.database_url = config["database_url"]

    async def start(self):
        logger.info(
            f"Starting Shelly 1st Gen instance_name={self.instance_name} url={self.url} poll_period_sec={self.poll_period}"
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
        response = await client.get(self.url)
        if response.status_code == 200:
            res = response.json()

            metrics = prometheus.Metrics()

            samples = metrics.gauge("electric_power_w", "Instantaneous power in Watt.")
            samples.add(res["emeters"][0]["power"], labels={"phase": "1", "sensor": "energymeter-house"})
            samples.add(res["emeters"][1]["power"], labels={"phase": "2", "sensor": "energymeter-house"})
            samples.add(res["emeters"][2]["power"], labels={"phase": "3", "sensor": "energymeter-house"})
            samples.add(
                res["emeters"][0]["power"] + res["emeters"][1]["power"] + res["emeters"][2]["power"],
                labels={"phase": "all", "sensor": "energymeter-house"},
            )

            samples = metrics.counter("electric_consumption_kwh", "Total consumed energy in kWh.")
            samples.add(res["emeters"][0]["total"] / 1000, labels={"phase": "1", "sensor": "energymeter-house"})
            samples.add(res["emeters"][1]["total"] / 1000, labels={"phase": "2", "sensor": "energymeter-house"})
            samples.add(res["emeters"][2]["total"] / 1000, labels={"phase": "3", "sensor": "energymeter-house"})
            samples.add(
                (res["emeters"][0]["total"] + res["emeters"][1]["total"] + res["emeters"][2]["total"]) / 1000,
                labels={"phase": "all", "sensor": "energymeter-house"},
            )

            samples = metrics.gauge("electric_current_a", "Current in Amps")
            samples.add(res["emeters"][0]["current"], labels={"phase": "1", "sensor": "energymeter-house"})
            samples.add(res["emeters"][1]["current"], labels={"phase": "2", "sensor": "energymeter-house"})
            samples.add(res["emeters"][2]["current"], labels={"phase": "3", "sensor": "energymeter-house"})
            samples.add(
                res["emeters"][0]["current"] + res["emeters"][1]["current"] + res["emeters"][2]["current"],
                labels={"phase": "all", "sensor": "energymeter-house"},
            )

            samples = metrics.gauge("electric_voltage_v", "RMS voltage in Volts")
            samples.add(res["emeters"][0]["voltage"], labels={"phase": "1", "sensor": "energymeter-house"})
            samples.add(res["emeters"][1]["voltage"], labels={"phase": "2", "sensor": "energymeter-house"})
            samples.add(res["emeters"][2]["voltage"], labels={"phase": "3", "sensor": "energymeter-house"})

        else:
            raise task.TaskException(f"failed to fetch data: {response.status_code}")

        logger.info(f"Storing metrics: url={self.database_url}")
        await client.post(self.database_url, content=metrics.format())


task.register(Shelly1, "shelly1")
