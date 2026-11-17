import datetime
import time

from publishers.base_publisher import BasePublisher
from publishers.gps_time import gps_time
from publishers.logger import Logger
from sensors.connection_strategy import ConnectionStrategy
from sensors.picarro import Picarro


class GasPublisher(BasePublisher):
    def __init__(self,
                 connection: ConnectionStrategy,
                 logger: Logger,
                 gas_inlet_delay: float,
                 url: str = 'http://127.0.0.1:5000/measurement/gas'):
        super().__init__('Gas', url, logger)
        self._picarro = Picarro(connection)
        self._gas_inlet_delay = datetime.timedelta(seconds=gas_inlet_delay)

    def start_up(self) -> None:
        self._picarro.connect()
        status = self._picarro.Instr_GetStatus()
        self._logger.log(f"Instrument status:\n{status}")
        self._picarro.Meas_ClearBuffer()
        self._logger.log("Waiting for GPS time...")
        gps_time.wait_for_gps_initialization()
        self._logger.log("Acquired GPS time")

    def measurement_routine(self) -> None:
        ch4, co2, h2o = self._picarro.Meas_GetBuffer()

        for gas in [ch4, co2, h2o]:
            for measurement in gas:
                measurement.datetime = measurement.datetime - self._gas_inlet_delay
                self._try_post_measurement_to_server(measurement)
        time.sleep(2)

    def shutdown(self) -> None:
        self._picarro.close()
