import asyncio
import logging

import httpx
import prometheus
import task
import utils

logger = logging.getLogger("app.goe-charger")


class GoECharger(object):
    def configure(self, instance_name, config):
        self.instance_name = instance_name
        self.url = config["url"]
        self.database_url = config["database_url"]
        self.poll_period = utils.parse_timedelta(config.get("poll-period", "1h"))

    async def start(self):
        logger.info(
            "Starting Go-e instance_name={self.instance_name} goe_url={self.goe_url} poll_period_sec={self.poll_period}"
        )

        while True:
            await self.update_metrics()

            logger.info(f"Sleeping for {self.poll_period}")
            await asyncio.sleep(self.poll_period.total_seconds())

    async def update_metrics(self):
        logger.debug(f"Fetching data: url={self.url}")

        client = httpx.AsyncClient()
        response = await client.get(self.url)
        if response.status_code == 200:
            res = response.json()

            metrics = prometheus.Metrics()

            samples = metrics.counter("electric_consumption_kwh", "Total consumed energy (kWh)")
            samples.add(res["eto"] / 1000, labels={"sensor": "car-charger", "phase": "all"})

            samples = metrics.gauge(
                "electric_power_w",
                "Instantaneous power (Watt)",
                labels={"sensor": "car-charger"},
            )
            samples.add(res["nrg"][7], labels={"sensor": "car-charger", "phase": "1"})
            samples.add(res["nrg"][8], labels={"sensor": "car-charger", "phase": "2"})
            samples.add(res["nrg"][9], labels={"sensor": "car-charger", "phase": "3"})
            samples.add(res["nrg"][11], labels={"sensor": "car-charger", "phase": "all"})

            samples = metrics.gauge(
                "electric_current_a",
                "Current (Amps)",
                labels={"sensor": "car-charger"},
            )
            samples.add(res["nrg"][4], labels={"phase": "1"})
            samples.add(res["nrg"][5], labels={"phase": "2"})
            samples.add(res["nrg"][6], labels={"phase": "3"})
            samples.add(res["nrg"][4] + res["nrg"][5] + res["nrg"][6], labels={"phase": "all"})

            samples = metrics.gauge(
                "electric_voltage_v",
                "RMS voltage (Volts)",
                labels={"sensor": "car-charger"},
            )
            samples.add(res["nrg"][0], labels={"phase": "1"})
            samples.add(res["nrg"][1], labels={"phase": "2"})
            samples.add(res["nrg"][2], labels={"phase": "3"})

            is_charging = "true" if res["car"] == 2 else "false"

            if is_charging:
                samples = metrics.gauge(
                    "charging_time_since_connected_min",
                    "Charging duration since session started (minutes)",
                    labels={"sensor": "car-charger"},
                )
                samples.add(int(res["cdi"]["value"] / (1000 * 60)) if res["cdi"]["type"] == 1 else 0)

                samples = metrics.gauge(
                    "charging_energy_since_connected_kwh",
                    "Energy charged since session started (kWh)",
                    labels={"sensor": "car-charger"},
                )
                samples.add(res["wh"] / 1000)

        else:
            raise task.TaskException(f"failed to fetch data: {response.status_code}")

        logger.info(f"Storing metrics: url={self.database_url}")
        await client.post(self.database_url, content=metrics.format())


task.register(GoECharger, "goe-charger")
