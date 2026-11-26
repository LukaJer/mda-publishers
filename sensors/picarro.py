from datetime import datetime
from typing import List, Tuple

from messages.gas_measurement_message import GasMeasurement
from sensors.connection_strategy import ConnectionStrategy


class InstrumentStatus:
    def __init__(self, status: int) -> None:
        self.SystemError = bool(status & 16384)
        self.WarmingUp = bool(status & 8192)
        self.PressureLocked = bool(status & 128)
        self.GasFlowing = bool(status & 64)
        self.MeasurementInBuffer = bool(status & 32)
        self.NewMeasAvailable = bool(status & 16)
        self.ErrorInBuffer = bool(status & 4)
        self.MeasActive = bool(status & 2)
        self.Ready = bool(status & 1)

    def __str__(self) -> str:
        repr = ""

        if self.SystemError:
            repr += "A system error is present. Use _Instr_GetError for more information.\n"
        else:
            repr += "The instrument is not currently in an error state.\n"

        if self.WarmingUp:
            repr += "The instrument is currently warming up from power-off or restart.\n"
        else:
            repr += "The instrument has successfully started up.\n"

        if self.PressureLocked:
            repr += "The gas sample pressure is within acceptable bounds for measurements.\n"
        else:
            repr += "The gas sample pressure is not stabilized within acceptable bounds.\n"

        if self.GasFlowing:
            repr += "Valves are open and pump is on (pressure not necessarily stable).\n"
        else:
            repr += "Valves are closed and no gas is flowing.\n"

        if self.MeasurementInBuffer:
            repr += "Measurements available in measurement buffer.\n"
        else:
            repr += "Measurement buffer is empty.\n"

        if self.NewMeasAvailable:
            repr += "New measurement has been made since last read.\n"
        else:
            repr += "No new data are available since last read.\n"

        if self.ErrorInBuffer:
            repr += "There is at least one value in the error queue.\n"
        else:
            repr += "The error queue is empty.\n"

        if self.MeasActive:
            repr += "The measurement system is currently active.\n"
        else:
            repr += "The measurement system is currently inactive.\n"

        if self.Ready:
            repr += "The instrument is currently capable of measuring the sample gas."
        else:
            repr += "The instrument currently cannot make a gas measurement."

        return repr


class Picarro:
    TERMINATION_CHARACTER = b'\r'
    ERROR_CODE_DESCRIPTIONS = {
        1000: "Communication failed",
        1001: "Processing previous command",
        1002: "Command not recognized",
        1003: "Parameters invalid",
        1004: "Command execution failed",

        2000: "General system error",
        2001: "Thermal systems not locked",
        2002: "Ambient temperature outside recommended ranges",

        3000: "General Measurement System error",
        3001: "Measurement system disabled",
        3002: "No measurement data exists",
        3003: "Requested buffering rate out of range",

        4000: "General Gas Management System error",
        4001: "Gas already flowing",
        4002: "Flow stopped; can't enable measurement system",
        4003: "Pressure not stabilized",
        4004: "Pump disabled; can't start flow",

        5000: "General EIF System error",
        5001: "Invalid channel specified (for Electrical Interface)",
        5002: "Requested output level out of range",

        6001: "No pulse analyzer data exists.",
        6002: "Pulse analyzer is not running."
    }

    def __init__(self, connection_strategy: ConnectionStrategy) -> None:
        self._connection = connection_strategy

    def connect(self, retries: int = 0, delay: int = 2, stop_event=None) -> None:
        self._connection.connect(retries=retries, delay=delay, stop_event=stop_event)

    def _exec_cmd(self, cmd: str = None) -> str:
        if cmd:
            self._connection.write(cmd)
        buffer = self._connection.read()

        if self._is_error(buffer):
            self._raise_error(buffer, cmd)
        return buffer.decode()

    def close(self) -> None:
        self._connection.close()

    def _is_error(self, buffer: bytes) -> bool:
        return buffer[:4] == b"ERR:"

    def _get_error_code(self, buffer: bytes) -> int:
        return int(buffer[4:8])

    def _raise_error(self, buffer: bytes, cmd: str) -> None:
        error_code = self._get_error_code(buffer)
        if error_code in self.ERROR_CODE_DESCRIPTIONS.keys():
            raise Exception(f"Command '{cmd}' returned error '{self.ERROR_CODE_DESCRIPTIONS[error_code]}'")
        raise Exception(f"Command '{cmd}' returned an unknown error '{buffer.decode()}'")

    def Meas_GetConcEx(self) -> str:
        data = self._exec_cmd("_Meas_GetConcEx")

        for split in data.split(';'):
            print(split)
        return data

    def Instr_GetStatus(self) -> InstrumentStatus:
        return InstrumentStatus(int(self._exec_cmd("_Instr_GetStatus")))

    def Meas_ClearBuffer(self) -> str:
        return self._exec_cmd("_Meas_ClearBuffer")

    def Meas_GetBuffer(self) -> Tuple[List[GasMeasurement], List[GasMeasurement], List[GasMeasurement]]:
        ch4_measurements = []
        co2_measurements = []
        h2o_measurements = []

        buffer_size = int(self._exec_cmd("_Meas_GetBuffer").strip(";\r\n "))
        for _ in range(buffer_size):
            buffer = self._exec_cmd().strip(";\r\n ").split(";")

            ch4_measurements.append(GasMeasurement(
                datetime=datetime.fromisoformat(buffer[0]),
                type='CH4',
                concentration=float(buffer[5]),
                unit="ppm"
            ))

            co2_measurements.append(GasMeasurement(
                datetime=datetime.fromisoformat(buffer[0]),
                type='CO2',
                concentration=float(buffer[4]),
                unit="ppm"
            ))

            h2o_measurements.append(GasMeasurement(
                datetime=datetime.fromisoformat(buffer[0]),
                type='H2O',
                concentration=float(buffer[6]),
                unit="%"
            ))

        return ch4_measurements, co2_measurements, h2o_measurements

    def Meas_GetBufferFirst(self) -> str:
        return self._exec_cmd("_Meas_GetBufferFirst")
