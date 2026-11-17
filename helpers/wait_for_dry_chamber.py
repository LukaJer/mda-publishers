import subprocess
import time
from datetime import datetime

from publishers.logger import Logger
from sensors.connection_strategy import TcpConnectionStrategy
from sensors.picarro import Picarro

H2O_THRESHOLD = 0.002


def main():
    gas_logger = Logger('Gas')
    connection = TcpConnectionStrategy("192.168.0.104", 51020, gas_logger)
    picarro = Picarro(connection)
    picarro.connect()

    status = picarro.Instr_GetStatus()
    print(f"Instrument status:\n{status}")

    picarro.Meas_ClearBuffer()

    try:
        while True:
            now = datetime.now().strftime("%H:%M:%S.%f")
            print(f"{now} Querying data...")
            ch4, co2, h2o = picarro.Meas_GetBuffer()

            for gas in [ch4, co2, h2o]:
                for measurement in gas:
                    print(f"{now} {measurement}")
                    if measurement.type == "H2O" and measurement.concentration < H2O_THRESHOLD:
                        subprocess.run([
                            "/usr/bin/notify-send",
                            "--icon=info",
                            f"The H2O concentration is below {H2O_THRESHOLD}%"])
                        picarro.close()
                        exit()

            time.sleep(0.5)

    except KeyboardInterrupt:
        picarro.close()


if __name__ == "__main__":
    main()
