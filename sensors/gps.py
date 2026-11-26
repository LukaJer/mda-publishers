import math
import time
from datetime import timedelta

import pynmea2
from serial import Serial
from serial.serialutil import SerialException

from messages.location_measurement_message import LocationMeasurementMessage
from publishers.logger import Logger


class GPS:
    MAX_JUMP_SPEED_MPS = 100.0  # ~360 km/h; rejects multipath/cold-start spikes
    MIN_JUMP_ALLOWANCE_M = 50.0  # allow minor jitter when dt < 0.5s
    RECOVERY_CONSECUTIVE_FIXES = 3

    def __init__(self, serial_port: str, logger: Logger):
        self._port = serial_port
        self._serial = Serial()
        self._serial.port = serial_port
        self._serial.timeout = 1.0

        self._logger = logger
        self.last_status: str = "Initializing"
        self._last_valid_fix = None  # (datetime, lat, lon)
        self._candidate_fix = None   # (datetime, lat, lon, count)

    @staticmethod
    def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        r = 6371000.0
        p1, p2 = math.radians(lat1), math.radians(lat2)
        dp = math.radians(lat2 - lat1)
        dl = math.radians(lon2 - lon1)
        a = math.sin(dp / 2.0) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2.0) ** 2
        return 2.0 * r * math.atan2(math.sqrt(a), math.sqrt(max(0.0, 1.0 - a)))

    def _is_plausible_fix(self, measurement: LocationMeasurementMessage) -> bool:
        lat = measurement.latitude
        lon = measurement.longitude
        if not (math.isfinite(lat) and math.isfinite(lon)):
            return False
        if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
            return False
        if abs(lat) < 1e-6 and abs(lon) < 1e-6:
            return False

        if not math.isfinite(measurement.speed) or measurement.speed < 0:
            measurement.speed = 0.0
        if not math.isfinite(measurement.heading):
            measurement.heading = 0.0

        if self._last_valid_fix is None:
            self._last_valid_fix = (measurement.datetime, lat, lon)
            self._candidate_fix = None
            return True

        prev_dt, prev_lat, prev_lon = self._last_valid_fix
        dt_s = max(0.0, (measurement.datetime - prev_dt).total_seconds())
        dist_m = self._haversine_m(prev_lat, prev_lon, lat, lon)
        max_dist_m = max(self.MIN_JUMP_ALLOWANCE_M, self.MAX_JUMP_SPEED_MPS * dt_s)

        if dist_m <= max_dist_m:
            self._last_valid_fix = (measurement.datetime, lat, lon)
            self._candidate_fix = None
            return True

        # Track consecutive consistent fixes in case the previous baseline was wrong
        if self._candidate_fix is not None:
            c_dt, c_lat, c_lon, count = self._candidate_fix
            c_dt_s = max(0.0, (measurement.datetime - c_dt).total_seconds())
            c_dist_m = self._haversine_m(c_lat, c_lon, lat, lon)
            if c_dist_m <= max(self.MIN_JUMP_ALLOWANCE_M, self.MAX_JUMP_SPEED_MPS * c_dt_s):
                count += 1
                if count >= self.RECOVERY_CONSECUTIVE_FIXES:
                    self._last_valid_fix = (measurement.datetime, lat, lon)
                    self._candidate_fix = None
                    return True
                self._candidate_fix = (measurement.datetime, lat, lon, count)
                return False

        self._candidate_fix = (measurement.datetime, lat, lon, 1)
        self._logger.log(
            f"Rejected GPS glitch jump: {dist_m:.1f}m in {dt_s:.1f}s "
            f"(lat={lat:.6f}, lon={lon:.6f})"
        )
        return False

    def connect(self, retries: int = 0, delay: int = 2, stop_event=None) -> None:
        attempts = 0
        while retries == 0 or attempts < retries:
            if stop_event is not None and stop_event.is_set():
                return
            try:
                if self._serial.is_open:
                    self._serial.close()
                self._serial.open()
                return
            except SerialException as e:
                attempts += 1
                self._logger.log(f"Attempt {attempts} failed to open port '{self._port}': {e}. "
                                 f"Retrying in {delay} seconds...")
                if stop_event is not None:
                    if stop_event.wait(delay):
                        return
                else:
                    time.sleep(delay)
        raise SerialException(f"Could not open the serial port {self._port} after {retries} attempts.")

    def get_location_measurement(self):
        line = self._serial.readline().decode('utf-8', errors='replace').strip()
        if line.startswith('$'):
            msg = pynmea2.parse(line)
            if isinstance(msg, pynmea2.types.talker.RMC):
                if getattr(msg, 'status', None) != 'A' or msg.datestamp is None or msg.timestamp is None:
                    self.last_status = "Waiting for GPS fix"
                    return None
                measurement = LocationMeasurementMessage.create_from_NMEA_RMC(msg)
                if not self._is_plausible_fix(measurement):
                    self.last_status = "Waiting for valid GPS fix"
                    return None
                self.last_status = "OK"
                return measurement

    def close(self) -> None:
        self._serial.close()

    @staticmethod
    def _get_utc_offset() -> timedelta:
        if time.localtime().tm_isdst > 0:
            utc_offset_seconds = -time.altzone
        else:
            utc_offset_seconds = -time.timezone

        return timedelta(seconds=utc_offset_seconds)


