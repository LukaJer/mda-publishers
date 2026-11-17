import dataclasses
from datetime import datetime


@dataclasses.dataclass
class LogMessage:
    datetime: datetime
    sensor: str
    description: str

    def serialize(self) -> dict:
        return {
            "datetime": str(self.datetime),
            "sensor": self.sensor,
            "description": self.description,
        }

    def __str__(self) -> str:
        return f"Log(datetime={self.datetime}, sensor={self.sensor}, log={self.description})"
    