import time
from datetime import timedelta

import pynmea2
from serial import Serial
from serial.serialutil import SerialException

from messages.location_measurement_message import LocationMeasurementMessage
from publishers.logger import Logger


class GPS:
    def __init__(self, serial_port: str, logger: Logger):
        self._port = serial_port
        self._serial = Serial()
        self._serial.port = serial_port
        self._serial.timeout = 1.0

        self._logger = logger
        self.last_status: str = "Initializing"

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
                self.last_status = "OK"
                return LocationMeasurementMessage.create_from_NMEA_RMC(msg)

    def close(self) -> None:
        self._serial.close()

    @staticmethod
    def _get_utc_offset() -> timedelta:
        if time.localtime().tm_isdst > 0:
            utc_offset_seconds = -time.altzone
        else:
            utc_offset_seconds = -time.timezone

        return timedelta(seconds=utc_offset_seconds)


