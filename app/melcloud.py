import asyncio
import logging

import datetime
import httpx
import prometheus
import task

MELCLOUD_URI = "https://app.melcloud.com/Mitsubishi.Wifi.Client"
APP_VERSION = "1.30.5.0"

logger = logging.getLogger("app.melcloud")


class Melcloud(object):
    def configure(self, instance_name, config):
        self.instance_name = instance_name if instance_name else "melcloud"
        self.username = config["username"]
        self.password = config["password"]
        self.poll_period_sec = config.get("poll-period-sec", 60 * 60)
        self.database_url = config["database_url"]

    async def start(self):
        logger.info(f"Starting Melcloud instance_name={self.instance_name} poll_period_sec={self.poll_period_sec}")

        while True:
            try:
                await self.update_metrics()
            except Exception as e:
                logger.exception("Error:", exc_info=e)
                await asyncio.sleep(60)

            logger.info(f"Sleeping for {self.poll_period_sec} seconds")
            await asyncio.sleep(self.poll_period_sec)

    async def update_metrics(self):
        logger.debug(f"loggin in: username={self.username} password={'<redacted>' if self.password else 'None'}")

        client = httpx.AsyncClient()
        response = await client.post(
            f"{MELCLOUD_URI}/Login/ClientLogin",
            json={
                "AppVersion": APP_VERSION,
                "Email": self.username,
                "Password": self.password,
            },
        )
        if response.status_code != 200:
            logger.error(f"failed to login: {response.status_code}")
            raise task.TaskException(f"failed to login: {response.status_code}")

        res = response.json()
        if res["ErrorId"]:
            logger.error(f"failed to login ErrorId={res['ErrorId']} ErrorMessagre={res['ErrorMessage']}")
            raise task.TaskException(f"failed to login ErrorId={res['ErrorId']} ErrorMessagre={res['ErrorMessage']}")

        logger.debug(f"getting devices")
        response = await client.get(
            f"{MELCLOUD_URI}/User/ListDevices",
            headers={
                "X-Mitscontextkey": res["LoginData"]["ContextKey"],
            },
        )

        if response.status_code != 200:
            logger.error(f"failed to get devices: {response.status_code}")
            raise task.TaskException(f"failed to get devices: {response.status_code}")

        res = response.json()
        dev = res[0]["Structure"]["Devices"][0]["Device"]

        last_report = datetime.datetime.fromisoformat(dev["LastTimeStamp"])
        timestamp = last_report.timestamp() * 1000

        metrics = prometheus.Metrics()

        metrics.gauge(
            "temperature_celsius",
            "Temperature in Celsius",
            labels={"sensor": self.instance_name},
        ).add(dev["RoomTemperature"], timestamp_msec=timestamp)

        metrics.gauge(
            "target_temperature_celsius",
            "Target temperature in Celsius",
            labels={"sensor": self.instance_name},
        ).add(dev["SetTemperature"], timestamp_msec=timestamp)

        metrics.gauge(
            "electric_consumption_kwh", "Energy consumption in kWh", labels={"sensor": self.instance_name}
        ).add(dev["CurrentEnergyConsumed"] / 1000, timestamp_msec=timestamp)

        logger.info(f"Storing metrics: url={self.database_url}")
        await client.post(self.database_url, content=metrics.format())


task.register(Melcloud, "melcloud")
