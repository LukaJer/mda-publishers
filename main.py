import json
import os
import signal
import threading
import time

from publishers.logger import Logger
from sensors.connection_strategy import SerialConnectionStrategy, TcpConnectionStrategy

from publishers.envea_gas_publisher import AC32ePublisher, CO12ePublisher, O342ePublisher
from publishers.gas_publisher import GasPublisher
from publishers.grimm_publisher import GrimmPublisher
from publishers.gps_publisher import GpsPublisher
from publishers.wind_publisher import WindPublisher


DEVICES_CONFIG_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "devices.json")
)


def load_devices_config() -> dict:
    with open(DEVICES_CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def build_publishers():
    cfg = load_devices_config()
    gas_logger = Logger("Gas")
    pm_logger = Logger("PM")
    picarro_logger = Logger("Picarro")

    publishers = []

    envea_map = [
        ("AC32e", AC32ePublisher),
        ("O342e", O342ePublisher),
        ("CO12e", CO12ePublisher),
    ]
    for key, cls in envea_map:
        d = cfg.get(key, {})
        if d.get("enabled", False):
            publishers.append(
                cls(
                    connection=None,
                    logger=gas_logger,
                    mode=d.get("mode", "modbus"),
                    modbus_host=d["host"],
                    modbus_port=d.get("port", 502),
                    interval=d.get("interval", 1.0),
                )
            )

    grimm_cfg = cfg.get("Grimm11D", {})
    if grimm_cfg.get("enabled", False):
        grimm_conn = SerialConnectionStrategy(grimm_cfg["port"], pm_logger)
        publishers.append(
            GrimmPublisher(grimm_conn, pm_logger, interval=grimm_cfg.get("interval", 6.0))
        )

    picarro_cfg = cfg.get("Picarro", {})
    if picarro_cfg.get("enabled", False):
        picarro_conn = TcpConnectionStrategy(
            picarro_cfg["host"], picarro_cfg.get("port", 51020), picarro_logger
        )
        publishers.append(
            GasPublisher(
                picarro_conn,
                picarro_logger,
                gas_inlet_delay=picarro_cfg.get("inlet_delay", 11),
                interval=picarro_cfg.get("interval", 2.0),
            )
        )

    gps_cfg = cfg.get("GPS", {})
    if gps_cfg.get("enabled", False):
        publishers.append(GpsPublisher(gps_cfg["port"], Logger("GPS")))

    wind_cfg = cfg.get("Wind", {})
    if wind_cfg.get("enabled", False):
        publishers.append(
            WindPublisher(
                wind_cfg["port"],
                Logger("Wind"),
                interval=wind_cfg.get("interval", 1.0),
            )
        )

    return publishers


def main():
    publishers = build_publishers()
    if not publishers:
        print("No devices enabled in devices.json.")
        return

    stop_event = threading.Event()

    for p in publishers:
        p.daemon = True
        p.start()

    def handle_stop(signum, frame):
        if stop_event.is_set():
            os._exit(130)
        stop_event.set()
        for p in publishers:
            p.stop()

    signal.signal(signal.SIGINT, handle_stop)
    signal.signal(signal.SIGTERM, handle_stop)

    while any(p.is_alive() for p in publishers):
        if stop_event.is_set():
            deadline = time.monotonic() + 2.0
            for p in publishers:
                remaining = max(0.0, deadline - time.monotonic())
                p.join(timeout=remaining)
            break
        time.sleep(0.2)


if __name__ == "__main__":
    main()
