import pynmea2

from publishers.base_publisher import BasePublisher
from publishers.gps_time import gps_time
from publishers.logger import Logger
from sensors.gps import GPS


class GpsPublisher(BasePublisher):
    def __init__(self,
                 port: str,
                 logger: Logger,
                 url: str = 'http://127.0.0.1:5000/measurement/location'):
        super().__init__('GPS', url, logger)
        self._gps = GPS(port, logger)

    def start_up(self) -> None:
        self._gps.connect()

    def measurement_routine(self) -> None:
        try:
            measurement = self._gps.get_location_measurement()
            if measurement:
                gps_time.now = measurement.datetime
                self._try_post_measurement_to_server(measurement)
        except pynmea2.ParseError as e:
            self._logger.log(f"Parse error: '{e}'")
        except Exception as e:
            self._logger.log(f"Unknown exception occurred: '{e}'")

    def shutdown(self) -> None:
        self._gps.close()
