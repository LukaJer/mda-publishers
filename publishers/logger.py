from datetime import datetime

import requests

from messages.log_message import LogMessage


class Logger:
    def __init__(self, sensor_name: str, log_url: str = 'http://127.0.0.1:5000/measurement/log'):
        self._sensor_name = sensor_name
        self._log_url = log_url

    def log(self, log) -> None:
        log_msg = LogMessage(datetime.now(), self._sensor_name, log)
        try:
            requests.post(url=self._log_url, json=log_msg.serialize())
        except requests.ConnectionError as e:
            print(f"Failed to POST log '{log_msg}' to server '{self._log_url}': {e}")
