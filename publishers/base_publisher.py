import threading
import time
from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Optional

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
        self._session_local = threading.local()
        self._sessions_lock = threading.Lock()
        self._all_sessions: List[requests.Session] = []

        self._stopping = threading.Event()

    def _get_session(self) -> requests.Session:
        """Return a thread-local requests.Session, tracking it for shutdown cleanup."""
        session = getattr(self._session_local, "session", None)
        if session is None:
            session = requests.Session()
            self._session_local.session = session
            with self._sessions_lock:
                self._all_sessions.append(session)
        return session

    def _close_sessions(self) -> None:
        """Close every tracked thread-local HTTP session safely."""
        with self._sessions_lock:
            sessions = list(self._all_sessions)
            self._all_sessions.clear()
        for session in sessions:
            try:
                session.close()
            except Exception:
                pass
        self._session_local = threading.local()

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
            try:
                self.shutdown()
            except Exception as e:
                self._logger.log(f"Error during {self._sensor_name} shutdown: {e}")
            self._logger.log("Shutting down sensor...")
            self._try_post_log("Disconnected", only_on_change=False, timeout=1.0)
            self._close_sessions()

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

    def _post_json(self, url: str, payload, label: str, timeout: float = 5.0) -> None:
        """POST a JSON payload using the calling thread's keep-alive session."""
        try:
            resp = self._get_session().post(url=url, json=payload, timeout=timeout)
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
                      heartbeat_seconds: float = 30.0, timeout: float = 5.0) -> None:
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
        self._post_json(self._log_url, msg.serialize(), "log", timeout=timeout)

    def stop(self):
        self._stopping.set()
