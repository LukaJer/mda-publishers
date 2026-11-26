import threading
import time
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional

import requests

from messages.log_message import LogMessage
from publishers.gps_time import gps_time
from publishers.logger import Logger


class BasePublisher(threading.Thread, ABC):
    def __init__(self, sensor_name: str,
                 url: str, logger: Logger,
                 log_url: str = "http://127.0.0.1:5000/measurement/log"):
        super().__init__()
        self._logger = logger
        self._sensor_name = sensor_name
        self._url = url
        self._log_url = log_url
        self._last_log_description: Optional[str] = None
        self._last_log_sent_at: float = 0.0
        self._session = requests.Session()

        self._stopping = threading.Event()

    def run(self):
        self._logger.log("Starting sensor...")
        try:
            self.start_up()

            if not self._stopping.is_set():
                self._logger.log("Starting measurements...")
                while not self._stopping.is_set():
                    self.measurement_routine()
        except Exception as e:
            self._logger.log(f"Unhandled exception in {self._sensor_name}: {e}")
            self._try_post_log(f"ERROR: {e}")
        finally:
            self._logger.log("Shutting down sensor...")
            try:
                self.shutdown()
            except Exception as e:
                self._logger.log(f"Error during {self._sensor_name} shutdown: {e}")
            self._try_post_log("Disconnected", only_on_change=False)
            self._session.close()

    def _wait_for_gps_or_stop(self, poll_interval: float = 0.5) -> bool:
        """Wait for GPS time initialization unless stop() has been requested."""
        while not self._stopping.is_set():
            if gps_time.wait_for_gps_initialization(timeout=poll_interval):
                return True
        return False

    @abstractmethod
    def start_up(self):
        pass

    @abstractmethod
    def measurement_routine(self):
        pass

    @abstractmethod
    def shutdown(self):
        pass

    def _post_json(self, url: str, payload, label: str) -> None:
        """POST a JSON payload using the publisher's keep-alive session."""
        try:
            resp = self._session.post(url=url, json=payload, timeout=5.0)
            if not resp.ok:
                print(f"Warning: POST {self._sensor_name} {label} to '{url}' returned {resp.status_code}")
        except requests.RequestException as e:
            print(f"Failed to POST {self._sensor_name} {label} to server '{url}': {e}")

    def _try_post_measurement_to_server(self, measurement):
        self._post_json(self._url, measurement.serialize(), "measurement")

    def _try_post_measurements_batch(self, measurements) -> None:
        """POST a batch of measurements in one request when more than one is present."""
        if not measurements:
            return
        if len(measurements) == 1:
            self._try_post_measurement_to_server(measurements[0])
            return
        self._post_json(self._url, [m.serialize() for m in measurements], "measurement")

    def _try_post_log(self, description: str, only_on_change: bool = True,
                      heartbeat_seconds: float = 30.0) -> None:
        now_mono = time.monotonic()
        if (only_on_change and description == self._last_log_description
                and (now_mono - self._last_log_sent_at) < heartbeat_seconds):
            return
        self._last_log_description = description
        self._last_log_sent_at = now_mono
        try:
            now = gps_time.now
        except ValueError:
            now = datetime.now()
        msg = LogMessage(datetime=now, sensor=self._sensor_name, description=description)
        self._post_json(self._log_url, msg.serialize(), "log")

    def stop(self):
        self._stopping.set()
