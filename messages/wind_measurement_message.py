import dataclasses
from datetime import datetime


@dataclasses.dataclass
class WindMeasurementMessage:
    datetime: datetime
    speed: float
    heading: float

    def serialize(self) -> dict:
        return {
            "datetime": str(self.datetime),
            "heading": f"{self.heading:.1f}",
            "speed": f"{self.speed:.2f}",
        }

    @staticmethod
    def create(datetime_stamp: datetime, speed: float, heading: float) -> "WindMeasurementMessage":
        

        return WindMeasurementMessage(
            datetime=datetime_stamp,
            speed=speed,
            heading=heading
        )

    def __str__(self) -> str:
        return (f"Wind("
                f"datetime={self.datetime}, "
                f"speed={self.speed}, "
                f"heading={self.heading})")
