import configparser
import os
import signal
import threading
import time

from publishers.gas_publisher import GasPublisher
from publishers.gps_publisher import GpsPublisher
from publishers.li7810_publisher import LI7810Publisher
from publishers.logger import Logger
from publishers.wind_publisher import WindPublisher
from sensors.connection_strategy import TcpConnectionStrategy


def main():
    config = configparser.ConfigParser()
    config.read("config.ini")

    gas_sensor_ip_address = config.get('Settings', 'gas_sensor_ip_address', fallback=None)
    gas_sensor_inlet_delay = config.getint('Settings', 'gas_sensor_inlet_delay', fallback=0)
    wind_sensor_serial_port = config.get('Settings', 'wind_sensor_serial_port', fallback=None)
    location_sensor_serial_port = config.get('Settings', 'location_sensor_serial_port', fallback=None)
    li7810_hostname = config.get('Settings', 'li7810_hostname', fallback=None)
    li7810_gas_inlet_delay = config.getint('Settings', 'li7810_gas_inlet_delay', fallback=0)

    publishers = []

    if gas_sensor_ip_address:
        gas_logger = Logger('Gas')
        connection = TcpConnectionStrategy(gas_sensor_ip_address, 51020, gas_logger)
        gas_publisher = GasPublisher(
            connection=connection,
            gas_inlet_delay=gas_sensor_inlet_delay,
            logger=gas_logger,
            url='http://127.0.0.1:5000/measurement/gas')
        publishers.append(gas_publisher)

    if wind_sensor_serial_port:
        wind_logger = Logger('Wind')
        wind_publisher = WindPublisher(
            port=wind_sensor_serial_port,
            logger=wind_logger,
            url='http://127.0.0.1:5000/measurement/wind')
        publishers.append(wind_publisher)

    if location_sensor_serial_port:
        location_logger = Logger('Location')
        location_publisher = GpsPublisher(
            port=location_sensor_serial_port,
            logger=location_logger,
            url='http://127.0.0.1:5000/measurement/location')
        publishers.append(location_publisher)

    if li7810_hostname:
        li7810_logger = Logger('LI7810')
        li7810_publisher = LI7810Publisher(
            host=li7810_hostname,
            port=1883,
            gas_inlet_delay=li7810_gas_inlet_delay,
            logger=li7810_logger,
            url='http://127.0.0.1:5000/measurement/gas'
        )
        publishers.append(li7810_publisher)

    if len(publishers) == 0:
        print("At least one publisher must be active!")
        exit(1)

    stop_event = threading.Event()

    for publisher in publishers:
        publisher.daemon = True
        publisher.start()

    def handle_stop(signum, frame):
        if stop_event.is_set():
            os._exit(130)
        stop_event.set()
        for publisher in publishers:
            publisher.stop()

    signal.signal(signal.SIGINT, handle_stop)
    signal.signal(signal.SIGTERM, handle_stop)

    while any(publisher.is_alive() for publisher in publishers):
        if stop_event.is_set():
            deadline = time.monotonic() + 2.0
            for publisher in publishers:
                remaining = max(0.0, deadline - time.monotonic())
                publisher.join(timeout=remaining)
            break
        time.sleep(0.2)


if __name__ == "__main__":
    print(f"PID: {os.getpid()}")
    main()
