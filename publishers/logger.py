import threading

import requests

from messages.log_message import LogMessage
from publishers.gps_time import gps_time


class Logger:
    def __init__(self, sensor_name: str, log_url: str = 'http://127.0.0.1:5000/measurement/log'):
        self._sensor_name = sensor_name if sensor_name.endswith(":log") else f"{sensor_name}:log"
        self._log_url = log_url
        self._local = threading.local()

    def _get_session(self) -> requests.Session:
        """Return a thread-local requests.Session for safe HTTP keep-alive reuse."""
        session = getattr(self._local, "session", None)
        if session is None:
            session = requests.Session()
            self._local.session = session
        return session

    def log(self, log) -> None:
        log_msg = LogMessage(gps_time.now, self._sensor_name, log)
        try:
            self._get_session().post(url=self._log_url, json=log_msg.serialize(), timeout=5.0)
        except requests.RequestException as e:
            print(f"Failed to POST log '{log_msg}' to server '{self._log_url}': {e}")
