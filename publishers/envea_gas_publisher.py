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
        self._device.connect()
        self._logger.log("Waiting for GPS time...")
        gps_time.wait_for_gps_initialization()
        self._logger.log("Acquired GPS time")

    def measurement_routine(self) -> None:
        try:
            for measurement in self._device.read_measurements():
                self._try_post_measurement_to_server(measurement)
        except Exception as e:
            self._logger.log(f"Unknown exception occurred: '{e}'")
        time.sleep(self._interval)

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
