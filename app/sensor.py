import logging
from typing import Protocol, Type

logger = logging.getLogger("sensor")


# Interface for sensor classes.
class Sensor(Protocol):
    def configure(self, instance_name: str, config: dict) -> None:
        ...

    async def start(self) -> None:
        ...


class SensorException(Exception):
    pass


# Global registry of sensor classes.
sensor_classes: dict[str, Type[Sensor]] = {}


def register(cls: Type[Sensor], sensor_type: str):
    logger.debug(f"Registering sensor class: {sensor_type}")
    sensor_classes[sensor_type] = cls


def get_sensor_class(sensor_type: str) -> Type[Sensor]:
    return sensor_classes[sensor_type]
