import threading
from abc import ABC, abstractmethod

import requests

from publishers.logger import Logger


class BasePublisher(threading.Thread, ABC):
    def __init__(self, sensor_name: str,
                 url: str, logger: Logger):
        super().__init__()
        self._logger = logger
        self._sensor_name = sensor_name
        self._url = url

        self._stopping = threading.Event()

    def run(self):
        self._logger.log(f"Starting sensor...")
        self.start_up()

        self._logger.log(f"Starting measurements...")
        while not self._stopping.is_set():
            self.measurement_routine()

        self._logger.log(f"Shutting down sensor...")
        self.shutdown()

    @abstractmethod
    def start_up(self):
        pass

    @abstractmethod
    def measurement_routine(self):
        pass

    @abstractmethod
    def shutdown(self):
        pass

    def _try_post_measurement_to_server(self, measurement):
        try:
            requests.post(url=self._url, json=measurement.serialize())
        except requests.ConnectionError as e:
            print(f"Failed to POST {self._sensor_name} measurement to server '{self._url}': {e}")

    def stop(self):
        self._stopping.set()

