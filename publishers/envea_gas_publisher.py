import time

from publishers.base_publisher import BasePublisher
from publishers.gps_time import gps_time
from publishers.logger import Logger
from sensors.ac32e import AC32e
from sensors.co12e import CO12e
from sensors.o342e import O342e


class _EnveaPublisher(BasePublisher):
    def __init__(self, sensor_name, driver, logger, interval=1.0,
                 url="http://127.0.0.1:5000/measurement/gas"):
        super().__init__(sensor_name, url, logger)
        self._device = driver
        self._interval = interval

    def start_up(self) -> None:
        self._try_post_log("Unconnected")
        try:
            self._device.connect(stop_event=self._stopping)
        except Exception as e:
            self._logger.log(f"Initial connect failed: {e}")
            self._try_post_log(f"ERROR: {e}")
        if gps_time.is_initialized:
            self._logger.log("Acquired GPS time")
        else:
            self._logger.log("No GPS fix yet; using local system time until GPS is acquired")

    def measurement_routine(self) -> None:
        try:
            for measurement in self._device.read_measurements():
                self._try_post_measurement_to_server(measurement)
            self._try_post_log(self._device.last_status)
        except Exception as e:
            self._logger.log(f"Unknown exception occurred: '{e}'")
            self._try_post_log(f"ERROR: {e}")
        self._stopping.wait(self._interval)

    def shutdown(self) -> None:
        self._device.close()


class AC32ePublisher(_EnveaPublisher):
    def __init__(self, connection=None, logger: Logger = None, mode="stream",
                 interval=1.0, modbus_host=None, modbus_port=502,
                 url="http://127.0.0.1:5000/measurement/gas"):
        driver = AC32e(connection, mode=mode, logger=logger,
                       modbus_host=modbus_host, modbus_port=modbus_port)
        super().__init__("AC32e", driver, logger, interval, url)


class CO12ePublisher(_EnveaPublisher):
    def __init__(self, connection=None, logger: Logger = None, mode="stream",
                 interval=1.0, modbus_host=None, modbus_port=502,
                 url="http://127.0.0.1:5000/measurement/gas"):
        driver = CO12e(connection, mode=mode, logger=logger,
                       modbus_host=modbus_host, modbus_port=modbus_port)
        super().__init__("CO12e", driver, logger, interval, url)


class O342ePublisher(_EnveaPublisher):
    def __init__(self, connection=None, logger: Logger = None, mode="stream",
                 interval=1.0, modbus_host=None, modbus_port=502,
                 url="http://127.0.0.1:5000/measurement/gas"):
        driver = O342e(connection, mode=mode, logger=logger,
                       modbus_host=modbus_host, modbus_port=modbus_port)
        super().__init__("O342e", driver, logger, interval, url)
