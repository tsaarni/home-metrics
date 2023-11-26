import asyncio
import datetime
import logging

import prometheus
import task
import utils
from aiohttp import ClientSession
from skodaconnect import Connection

logger = logging.getLogger("skoda")


class Skoda(object):
    def configure(self, instance_name, config):
        self.instance_name = instance_name
        self.username = config["username"]
        self.password = config["password"]
        self.vin = config["vin"]
        self.api_debug = config.get("debug", False)
        self.schedule = datetime.datetime.strptime(config.get("schedule", "5:00"), "%H:%M").time()
        self.database_url = config["database_url"]

    async def start(self):
        logger.info(f"Starting Skoda instance_name={self.instance_name} vin={self.vin} schedule={self.schedule}")

        # Scrape once immediately and then schedule next scrape by waiting until wake up time.
        while True:
            try:
                await self.update_metrics()
            except Exception as e:
                logger.exception("Error:", exc_info=e)

            # TODO: If scraping fails, retry after a short delay instead of waiting until next scheduled time.

            # Schedule next scrape.
            await utils.wait_until([self.schedule])

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

            samples = metrics.gauge("state_of_charge_percent", "State of charge (%)", labels={"sensor": "car"})
            samples.add(res_charging_status["battery"]["stateOfChargeInPercent"], timestamp_msec=time_of_report)

            samples = metrics.gauge("range_km", "Estimated range (km)", labels={"sensor": "car"})
            samples.add(
                res_charging_status["battery"]["cruisingRangeElectricInMeters"] / 1000, timestamp_msec=time_of_report
            )

            logger.info(f"Storing metrics: url={self.database_url}")

            async with ClientSession() as request:
                await request.post(self.database_url, data=metrics.format())


task.register(Skoda, "skoda")
