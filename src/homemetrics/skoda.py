import asyncio
import datetime
import logging

import prometheus
import task
import utils
from aiohttp import ClientSession
from skodaconnect import Connection

logger = logging.getLogger("app.skoda")


class Skoda(object):
    def configure(self, instance_name, config):
        self.instance_name = instance_name
        self.username = config["username"]
        self.password = config["password"]
        self.vin = config["vin"]
        self.api_debug = config.get("debug", False)
        self.database_url = config["database_url"]
        self.poll_schedule = []
        for t in config.get("poll-schedule", ["0:00", "12:00"]):
            self.poll_schedule.append(datetime.datetime.strptime(t, "%H:%M").time())

    async def start(self):
        logger.info(
            f"Starting Skoda instance_name={self.instance_name} vin={self.vin} poll_schedule={self.poll_schedule}"
        )

        # Scrape once immediately and then schedule next scrape by waiting until wake up time.
        while True:
            await self.update_metrics()

            # Calculate next scheduled wakeup time.
            seconds_until_wakeup, next_wakeup = utils.next_wakeup(self.poll_schedule)
            delay = utils.random_jitter(seconds_until_wakeup)
            logger.info(f"Next wakeup at {next_wakeup}, sleeping for {delay} (jittered)")
            await asyncio.sleep(delay.total_seconds())

    async def update_metrics(self):
        # Create HTTP session.
        async with ClientSession() as session:
            # Create connection to Skoda Connect API.
            conn = Connection(session, self.username, self.password, self.api_debug)

            # Login with credentials.
            logger.debug(f'Logging in: username={self.username} password={"<redacted>" if self.password else "None"}')
            await conn.doLogin()

            # Get vehicle status.
            logger.debug(f"Getting vehicle status: vin={self.vin}")
            res_vehicle_status = await conn.getVehicleStatus(self.vin)
            logger.debug(f"Result: {res_vehicle_status}")

            # Get charging status.
            logger.debug(f"Getting changing status: vin={self.vin}")
            res_charging_status = await conn.getCharging(self.vin)
            logger.debug(f"Result: {res_charging_status}")

            # Create record of vehicle data to send to timeseries database.
            metrics = prometheus.Metrics()

            time_of_report = (
                datetime.datetime.fromisoformat(res_vehicle_status["vehicle_remote"]["capturedAt"]).timestamp() * 1000
            )

            samples = metrics.counter("odometer_km", "Odometer (km)", labels={"sensor": "car"})
            samples.add(res_vehicle_status["vehicle_remote"]["mileageInKm"], timestamp_msec=time_of_report)

            samples = metrics.gauge("battery_percentage", "State of charge (%)", labels={"sensor": "car"})
            samples.add(res_charging_status["battery"]["stateOfChargeInPercent"], timestamp_msec=time_of_report)

            samples = metrics.gauge("range_km", "Estimated range (km)", labels={"sensor": "car"})
            samples.add(
                res_charging_status["battery"]["cruisingRangeElectricInMeters"] / 1000, timestamp_msec=time_of_report
            )

            logger.info(f"Storing metrics: url={self.database_url}")

            async with ClientSession() as request:
                await request.post(self.database_url, data=metrics.format())


task.register(Skoda, "skoda")
