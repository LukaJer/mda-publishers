from typing import List, Optional, Tuple

from messages.gas_measurement_message import GasMeasurement
from publishers.gps_time import gps_time
from sensors.connection_strategy import ConnectionStrategy


class Grimm11D:
    NAME = "Grimm11D"

    
    PM_FIELDS: List[Tuple[int, str, str]] = [
        (2, "PM10", "ug/m3"),
        (3, "PM4", "ug/m3"),
        (4, "PM2.5", "ug/m3"),
        (5, "PM1", "ug/m3"),
    ]

    
    _MASS_PREFIXES = ("N", "M", "K")

    
    _MAX_SCAN_LINES = 60

    def __init__(self, connection: ConnectionStrategy, logger=None,
                 skip_zero: bool = True) -> None:
        self._connection = connection
        self._logger = logger
        self._skip_zero = skip_zero
        self.last_status: str = "Initializing"

    def connect(self, retries: int = 0, delay: int = 2) -> None:
        self._connection.connect(retries=retries, delay=delay)

    def close(self) -> None:
        self._connection.close()

    def read_measurements(self) -> List[GasMeasurement]:
        """Scan buffered lines until a usable mass line is found.

        Returns the PM measurements from the first usable mass line, or an empty
        list if no mass line appeared within _MAX_SCAN_LINES (e.g. nothing on the
        port this cycle).
        """
        for _ in range(self._MAX_SCAN_LINES):
            try:
                raw = self._connection.read().decode("utf-8", errors="replace").strip()
            except Exception as e:
                self._log(f"{self.NAME} read stopped: {e}")
                self.last_status = f"ERROR: {e}"
                return []

            if not self._is_mass_line(raw):
                continue

            measurements = self._parse_mass_line(raw)
            if not measurements:
                continue

            if self._skip_zero and all(m.concentration == 0.0 for m in measurements):
                self.last_status = "Warming up / Zeroing"
                continue

            self.last_status = "OK"
            return measurements

        return []

    def _is_mass_line(self, raw: str) -> bool:
        
        if len(raw) < 2:
            return False
        if raw[0] not in self._MASS_PREFIXES:
            return False
        first_token = raw.split(None, 1)[0]
        if ":" in first_token or ";" in first_token:
            return False  # count line
        if len(raw.split()) < 2:
            return False  # identifier with no data
        return True

    def _parse_mass_line(self, raw: str) -> List[GasMeasurement]:
        measurements: List[GasMeasurement] = []
        try:
            tokens = raw.split()
            values = tokens[1:]  # drop the identifier token
            timestamp = gps_time.now
            for field_index, pm_type, unit in self.PM_FIELDS:
                token = values[field_index - 1]  # 1-based -> 0-based
                value = float(token)             # 'NA' -> ValueError -> skip line
                measurements.append(
                    GasMeasurement(timestamp, pm_type, value, unit))
        except (ValueError, IndexError) as e:
            self._log(f"{self.NAME} parse issue on line {raw!r}: {e}")
            if "NA" in raw:
                self.last_status = "Warming up (NA)"
            else:
                self.last_status = f"ERROR: parse issue ({e})"
            return []
        return measurements

    def _log(self, message: str) -> None:
        if self._logger:
            self._logger.log(message)
        else:
            print(message)
