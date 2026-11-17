import dataclasses
from datetime import datetime


@dataclasses.dataclass
class GasMeasurement:
    datetime: datetime
    type: str
    concentration: float
    unit: str

    def serialize(self) -> dict:
        return {
            "datetime": str(self.datetime),
            "type": self.type,
            "concentration": self.concentration,
            "unit": self.unit
        }

    def __str__(self) -> str:
        return (f"Gas("
                f"datetime={self.datetime}, "
                f"type={self.type}, "
                f"concentration={self.concentration}, "
                f"unit={self.unit})"
                )
    