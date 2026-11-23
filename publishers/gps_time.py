import time
from datetime import datetime, timedelta
import threading


class _GnssTime:
    def __init__(self):
        self._lock = threading.Lock()
        self._gnss_time = None
        self._time_of_last_update = None
        self._is_initialized_by_gnss = threading.Event()

    @property
    def is_initialized(self) -> bool:
        return self._is_initialized_by_gnss.is_set()

    @property
    def now(self) -> datetime:
        if not self._is_initialized_by_gnss.is_set():
            return datetime.now()
        with self._lock:
            delay_since_last_update = timedelta(seconds=time.monotonic() - self._time_of_last_update)
            return self._gnss_time + delay_since_last_update

    @now.setter
    def now(self, t: datetime) -> None:
        with self._lock:
            self._gnss_time = t
            self._time_of_last_update = time.monotonic()
            self._is_initialized_by_gnss.set()

    def wait_for_gps_initialization(self, timeout: float | None = None) -> bool:
        return self._is_initialized_by_gnss.wait(timeout=timeout)


gps_time = _GnssTime()
