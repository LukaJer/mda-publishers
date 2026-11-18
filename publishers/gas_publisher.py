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
                 interval: float = 2.0,
                 url: str = 'http://127.0.0.1:5000/measurement/gas'):
        super().__init__('Picarro', url, logger)
        self._picarro = Picarro(connection)
        self._gas_inlet_delay = datetime.timedelta(seconds=gas_inlet_delay)
        self._interval = interval

    def start_up(self) -> None:
        self._try_post_log("Unconnected")
        self._picarro.connect()
        status = self._picarro.Instr_GetStatus()
        self._logger.log(f"Instrument status:\n{status}")
        self._picarro.Meas_ClearBuffer()
        if gps_time.is_initialized:
            self._logger.log("Acquired GPS time")
        else:
            self._logger.log("No GPS fix yet; using local system time until GPS is acquired")

    def measurement_routine(self) -> None:
        try:
            ch4, co2, h2o = self._picarro.Meas_GetBuffer()
            has_data = False
            for gas in [ch4, co2, h2o]:
                for measurement in gas:
                    measurement.datetime = measurement.datetime - self._gas_inlet_delay
                    self._try_post_measurement_to_server(measurement)
                    has_data = True

            if has_data:
                self._try_post_log("OK")
            else:
                status = self._picarro.Instr_GetStatus()
                if status.SystemError:
                    self._try_post_log("ERROR: Picarro system error")
                elif status.WarmingUp:
                    self._try_post_log("Warming up")
                elif not status.Ready:
                    self._try_post_log("Not ready")
                else:
                    self._try_post_log("OK")
        except Exception as e:
            self._logger.log(f"Unknown exception occurred: '{e}'")
            self._try_post_log(f"ERROR: {e}")
        time.sleep(self._interval)

    def shutdown(self) -> None:
        self._picarro.close()
