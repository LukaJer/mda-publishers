import dataclasses
from datetime import datetime, timedelta

from pynmea2 import RMC


@dataclasses.dataclass
class LocationMeasurementMessage:
    datetime: datetime
    latitude: float
    longitude: float
    accuracy: float = 0
    heading: float = 0
    speed: float = 0

    def serialize(self) -> dict:
        return {
            "datetime": str(self.datetime),
            "latitude": self.latitude,
            "longitude": self.longitude,
            "accuracy": self.accuracy,
            "heading": self.heading,
            "speed": self.speed,
        }

    @staticmethod
    def create_from_NMEA_RMC(rmc: RMC, utc_offset: timedelta) -> "LocationMeasurementMessage":
        speed = 0.0 if rmc.spd_over_grnd is None else (rmc.spd_over_grnd * 1.852) / 3.6
        heading = 0.0 if rmc.true_course is None else rmc.true_course

        return LocationMeasurementMessage(
            datetime=datetime.combine(rmc.datestamp, rmc.timestamp) + utc_offset,
            latitude=rmc.latitude,
            longitude=rmc.longitude,
            speed=speed,
            heading=heading
        )

    def __str__(self) -> str:
        return (f"Location("
                f"datetime={self.datetime}, "
                f"lat={self.latitude}, "
                f"long={self.longitude}, "
                f"accuracy={self.accuracy}, "
                f"heading={self.heading}, "
                f"speed={self.speed})")