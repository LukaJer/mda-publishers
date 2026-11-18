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
                 interval: float = 1.0,
                 url: str = 'http://127.0.0.1:5000/measurement/wind'):
        super().__init__('Wind', url, logger)
        self._umb = UMB(port, logger)
        self._interval = interval

    def start_up(self) -> None:
        self._try_post_log("Unconnected")
        self._umb.connect()
        if gps_time.is_initialized:
            self._logger.log("Acquired GPS time")
        else:
            self._logger.log("No GPS fix yet; using local system time until GPS is acquired")

    def measurement_routine(self) -> None:
        try:
            message = self._umb.get_wind_measurement()
            self._try_post_measurement_to_server(message)
            self._try_post_log("OK")
        except UMBError as e:
            self._logger.log(f"An error in the UMB protocol occured: {e}")
            self._try_post_log(f"ERROR: {e}")
        except Exception as e:
            self._logger.log(f"Unknown exception occurred: '{e}'")
            self._try_post_log(f"ERROR: {e}")
        time.sleep(self._interval)

    def shutdown(self) -> None:
        self._umb.close()
