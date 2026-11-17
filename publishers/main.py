import signal

from publishers.logger import Logger
from sensors.connection_strategy import SerialConnectionStrategy

from publishers.envea_gas_publisher import AC32ePublisher, CO12ePublisher, O342ePublisher
from publishers.grimm_publisher import GrimmPublisher
from publishers.gps_publisher import GpsPublisher
from publishers.wind_publisher import WindPublisher



AC32E_IP = "169.254.169.1"   # NO / NO2 / NOx
O342E_IP = "169.254.169.2"   # O3
CO12E_IP = "169.254.169.3"   # CO
MODBUS_PORT = 502            # from the screen

ENVEA_MODE = "modbus"        

# --- serial ports 
GRIMM_PORT = "/dev/ttyUSB0"  # Grimm 11-D (RS-232 via USB)
GPS_PORT = "/dev/ttyUSB1"    # GPS receiver
WIND_PORT = "/dev/ttyUSB2"   # wind sensor (RS-485 via USB)


def build_publishers():
    gas_logger = Logger("Gas")
    pm_logger = Logger("PM")

    
    ac32e = AC32ePublisher(connection=None, logger=gas_logger, mode=ENVEA_MODE,
                           modbus_host=AC32E_IP, modbus_port=MODBUS_PORT, interval=1.0)
    o342e = O342ePublisher(connection=None, logger=gas_logger, mode=ENVEA_MODE,
                           modbus_host=O342E_IP, modbus_port=MODBUS_PORT, interval=1.0)
    co12e = CO12ePublisher(connection=None, logger=gas_logger, mode=ENVEA_MODE,
                           modbus_host=CO12E_IP, modbus_port=MODBUS_PORT, interval=1.0)

    grimm_conn = SerialConnectionStrategy(GRIMM_PORT, pm_logger)
    grimm = GrimmPublisher(grimm_conn, pm_logger, interval=6.0)

    return [
        ac32e, o342e, co12e, grimm,
        
        GpsPublisher(GPS_PORT, Logger("GPS")),
        WindPublisher(WIND_PORT, Logger("Wind")),
    ]


def main():
    publishers = build_publishers()
    for p in publishers:
        p.start()

    def handle_stop(signum, frame):
        for p in publishers:
            p.stop()

    signal.signal(signal.SIGINT, handle_stop)
    signal.signal(signal.SIGTERM, handle_stop)

    for p in publishers:
        p.join()


if __name__ == "__main__":
	main()
