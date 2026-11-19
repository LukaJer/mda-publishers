import requests

from messages.log_message import LogMessage
from publishers.gps_time import gps_time


class Logger:
    def __init__(self, sensor_name: str, log_url: str = 'http://127.0.0.1:5000/measurement/log'):
        self._sensor_name = sensor_name if sensor_name.endswith(":log") else f"{sensor_name}:log"
        self._log_url = log_url

    def log(self, log) -> None:
        log_msg = LogMessage(gps_time.now, self._sensor_name, log)
        try:
            requests.post(url=self._log_url, json=log_msg.serialize(), timeout=5.0)
        except requests.RequestException as e:
            print(f"Failed to POST log '{log_msg}' to server '{self._log_url}': {e}")
