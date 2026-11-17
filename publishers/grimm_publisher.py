import time

from publishers.base_publisher import BasePublisher
from publishers.gps_time import gps_time
from publishers.logger import Logger
from sensors.connection_strategy import ConnectionStrategy
from sensors.grimm_11d import Grimm11D


class GrimmPublisher(BasePublisher):
    def __init__(self, connection: ConnectionStrategy, logger: Logger,
                 interval: float = 6.0,
                 url: str = "http://127.0.0.1:5000/measurement/gas"):
        super().__init__("Grimm11D", url, logger)
        self._device = Grimm11D(connection, logger=logger)
        self._interval = interval

    def start_up(self) -> None:
        self._try_post_log("Unconnected")
        self._device.connect()
        self._logger.log("Waiting for GPS time...")
        self._try_post_log("Waiting for GPS time")
        gps_time.wait_for_gps_initialization()
        self._logger.log("Acquired GPS time")

    def measurement_routine(self) -> None:
        try:
            for measurement in self._device.read_measurements():
                self._try_post_measurement_to_server(measurement)
            self._try_post_log(self._device.last_status)
        except Exception as e:
            self._logger.log(f"Unknown exception occurred: '{e}'")
            self._try_post_log(f"ERROR: {e}")
        time.sleep(self._interval)

    def shutdown(self) -> None:
        self._device.close()
