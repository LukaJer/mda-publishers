from datetime import datetime
from typing import List, Optional, Tuple

from messages.gas_measurement_message import GasMeasurement
from publishers.gps_time import gps_time
from sensors.connection_strategy import ConnectionStrategy


class EnveaAnalyzer:
    
    NAME: str = "Envea"
    SEPARATOR: str = ";"
    TIME_INDEX: Optional[int] = 0
    TIME_FORMAT: str = "%Y-%m-%d %H:%M:%S"
    GAS_FIELDS: List[Tuple[int, str, str]] = []   
    HEADER_MARKERS: Tuple[str, ...] = ()
    POLL_COMMAND: str = ""                         
    MODBUS_FIELDS: List[Tuple[int, str, str]] = [] 
    MODBUS_UNIT_ID: int = 1
    MODBUS_WORD_SWAP: bool = True
    MODBUS_STATUS_REGISTER: Optional[int] = None
    MODBUS_STATUS_LABELS: dict = {}

    def __init__(self,
                 connection: Optional[ConnectionStrategy] = None,
                 mode: str = "stream",
                 logger=None,
                 modbus_host: Optional[str] = None,
                 modbus_port: int = 502) -> None:
        self._connection = connection
        self._mode = mode
        self._logger = logger
        self._modbus_host = modbus_host
        self._modbus_port = modbus_port
        self._modbus_client = None
        self.last_status: str = "Initializing"

    
    def connect(self, retries: int = 0, delay: int = 2) -> None:
        if self._mode == "modbus":
            from pymodbus.client import ModbusTcpClient
            self._modbus_client = ModbusTcpClient(self._modbus_host,
                                                  port=self._modbus_port)
            if not self._modbus_client.connect():
                raise ConnectionError(
                    f"{self.NAME}: cannot reach Modbus "
                    f"{self._modbus_host}:{self._modbus_port}")
        else:
            self._connection.connect(retries=retries, delay=delay)

    def close(self) -> None:
        if self._mode == "modbus":
            if self._modbus_client is not None:
                self._modbus_client.close()
        else:
            self._connection.close()

    
    def read_measurements(self) -> List[GasMeasurement]:
        if self._mode == "modbus":
            return self._read_modbus()
        return self._read_text()

    
    def _read_text(self) -> List[GasMeasurement]:
        if self._mode == "poll" and self.POLL_COMMAND:
            self._connection.write(self.POLL_COMMAND)
        raw = self._connection.read().decode("utf-8", errors="replace").strip()
        return self._parse_line(raw)

    def _parse_line(self, raw: str) -> List[GasMeasurement]:
        measurements: List[GasMeasurement] = []
        if not raw:
            return measurements
        if any(marker in raw for marker in self.HEADER_MARKERS):
            return measurements

        try:
            if self.SEPARATOR.strip() == "":
                parts = raw.split()
            else:
                parts = [p.strip() for p in raw.split(self.SEPARATOR)]

            if self.TIME_INDEX is not None:
                timestamp = datetime.strptime(parts[self.TIME_INDEX],
                                              self.TIME_FORMAT)
            else:
                timestamp = gps_time.now

            for index, gas_type, unit in self.GAS_FIELDS:
                value = float(parts[index])
                measurements.append(
                    GasMeasurement(timestamp, gas_type, value, unit))

        except (ValueError, IndexError) as e:
            self._log(f"{self.NAME} parse error on line {raw!r}: {e}")

        return measurements

    
    def _read_modbus(self) -> List[GasMeasurement]:
        import struct
        measurements: List[GasMeasurement] = []
        timestamp = gps_time.now
        try:
            if self._modbus_client is None or not self._modbus_client.connected:
                self.connect()

            status_msg = "OK"
            if self.MODBUS_STATUS_REGISTER is not None:
                sr = self._modbus_client.read_holding_registers(
                    address=self.MODBUS_STATUS_REGISTER, count=1, slave=self.MODBUS_UNIT_ID)
                if sr.isError():
                    status_msg = f"ERROR: Modbus status register {self.MODBUS_STATUS_REGISTER}"
                else:
                    code = sr.registers[0]
                    if code != 0:
                        status_msg = self.MODBUS_STATUS_LABELS.get(code, f"Status code {code}")

            had_error = False
            for register, gas_type, unit in self.MODBUS_FIELDS:
                rr = self._modbus_client.read_holding_registers(
                    address=register, count=2, slave=self.MODBUS_UNIT_ID)
                if rr.isError():
                    self._log(f"{self.NAME} Modbus error at register {register}")
                    had_error = True
                    continue
                reg0, reg1 = rr.registers[0], rr.registers[1]

                if self.MODBUS_WORD_SWAP:
                    reg0, reg1 = reg1, reg0
                value = struct.unpack(">f", struct.pack(">HH", reg0, reg1))[0]
                measurements.append(
                    GasMeasurement(timestamp, gas_type, value, unit))

            if had_error and not measurements:
                self.last_status = "ERROR: Modbus read error"
            else:
                self.last_status = status_msg
        except Exception as e:
            self._log(f"{self.NAME} Modbus read failed: {e}")
            self.last_status = f"ERROR: {e}"
        return measurements

    
    def _log(self, message: str) -> None:
        if self._logger:
            self._logger.log(message)
        else:
            print(message)
