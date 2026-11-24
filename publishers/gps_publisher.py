import subprocess
import threading

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
        self._system_time_synced = False

    def _sync_system_time_once(self, dt) -> None:
        if self._system_time_synced:
            return
        self._system_time_synced = True
        ts = dt.strftime('%Y-%m-%d %H:%M:%S')

        def _run():
            try:
                res = subprocess.run(
                    ['sudo', '-n', 'date', '-s', ts],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if res.returncode == 0:
                    self._logger.log(f"Synced system time to GPS: {ts}")
                else:
                    err = (res.stderr or res.stdout or '').strip()
                    self._logger.log(f"Skipped system time sync (sudo -n date failed): {err}")
            except Exception as e:
                self._logger.log(f"Failed to sync system time: {e}")

        threading.Thread(target=_run, daemon=True).start()

    def start_up(self) -> None:
        self._try_post_log("Unconnected")
        self._gps.connect(stop_event=self._stopping)

    def measurement_routine(self) -> None:
        try:
            measurement = self._gps.get_location_measurement()
            if measurement:
                gps_time.now = measurement.datetime
                self._sync_system_time_once(measurement.datetime)
                self._try_post_measurement_to_server(measurement)
            self._try_post_log(self._gps.last_status)
        except pynmea2.ParseError as e:
            self._logger.log(f"Parse error: '{e}'")
            self._try_post_log(f"ERROR: NMEA parse error")
        except Exception as e:
            self._logger.log(f"Unknown exception occurred: '{e}'")
            self._try_post_log(f"ERROR: {e}")
            self._stopping.wait(1.0)

    def shutdown(self) -> None:
        self._gps.close()
