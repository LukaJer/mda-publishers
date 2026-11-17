from datetime import datetime, timedelta
from typing import List

import requests

from messages.gas_measurement_message import GasMeasurement

_FILE_PATH = 'picarro_data/CFADS2343-20240820-141310Z-DataLog_User_Sync.dat'
_SERVER_URL = 'http://127.0.0.1:5000/measurement/gas'
_START = datetime(2024, 8, 20, 16, 0)
_END = datetime(2024, 8, 20, 19, 10)
_INLET_DELAY = timedelta(seconds=20)


def get_measurements_from_csv(path: str) -> List[GasMeasurement]:
    measurements = []
    with open(path, 'r') as file:
        lines = file.readlines()
        column_names = lines[0].strip().split()

        for line in lines[1:]:
            columns = line.strip().split()
            measurement = GasMeasurement(
                datetime=datetime.strptime(f'{columns[0]} {columns[1]}', '%Y-%m-%d %H:%M:%S.%f') - _INLET_DELAY,
                type="CH4",
                concentration=float(columns[18]),
                unit="ppm"
            )
            measurements.append(measurement)
    return measurements


def main():
    measurements = get_measurements_from_csv(_FILE_PATH)

    for measurement in measurements:
        if _START < measurement.datetime < _END:
            try:
                requests.post(url=_SERVER_URL, json=measurement.serialize())
                print(f"Posted measurement {measurement} to server")
            except requests.ConnectionError as e:
                print(f"Failed to POST measurement {measurement} to server '{_SERVER_URL}': {e}")


if __name__ == "__main__":
    main()
