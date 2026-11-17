import time
from datetime import datetime

from messages.wind_measurement_message import WindMeasurementMessage
from publishers.base_publisher import BasePublisher
from publishers.gps_time import gps_time
from publishers.logger import Logger
from sensors.umb import UMB, UMBError


class WindPublisher(BasePublisher):
    def __init__(self,
                 port: str,
                 logger: Logger,
                 url: str = 'http://127.0.0.1:5000/measurement/wind'):
        super().__init__('Wind', url, logger)
        self._umb = UMB(port, logger)

    def start_up(self) -> None:
        self._umb.connect()
        self._logger.log("Waiting for GPS time...")
        gps_time.wait_for_gps_initialization()
        self._logger.log("Acquired GPS time")

    def measurement_routine(self) -> None:
        try:
            message = self._umb.get_wind_measurement()
            self._try_post_measurement_to_server(message)
        except UMBError as e:
            self._logger.log(f"An error in the UMB protocol occured: {e}")
        except Exception as e:
            self._logger.log(f"Unknown exception occurred: '{e}'")
        time.sleep(1)

    def shutdown(self) -> None:
        self._umb.close()
