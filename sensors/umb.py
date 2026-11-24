import time
import struct
from typing import Tuple

import serial

from messages.wind_measurement_message import WindMeasurementMessage
from publishers.gps_time import gps_time
from publishers.logger import Logger


# 400 - wind speed
# 401 - wind speed fast
# 403 - wind speed std. dev.

# 500 - wind direction
# 501 - wind direction fast
# 503 - wind direction std. dev.


class UMBStatus:
    _STATUS_CODES = {
        0: "Status: Kommando erfolgreich; kein Fehler; alles i.O.",
        16: "Status: unbekanntes Kommando; wird von diesen Gerät nicht unterstützt",
        17: "Status: ungültige Parameter",
        18: "Status: ungültige Header-Version",
        19: "Status: ungültige Version des Befehls",
        20: "Status: Passwort für Kommando falsch",
        32: "Status: Lesefehler",
        33: "Status: Schreibfehler",
        34: "Status: Länge zu groß; max. zulässige Länge wird in <maxlength> angegeben",
        35: "Status: ungültige Adresse / Speicherstelle",
        36: "Status: ungültiger Kanal",
        37: "Status: Kommando in diesem Modus nicht möglich",
        38: "Status: unbekanntes Test-/Abgleich-Kommando",
        39: "Status: Fehler bei der Kalibrierung",
        40: "Status: Gerät nicht bereit; z.B. Initialisierung / Kalibrierung läuft",
        41: "Status: Unterspannung",
        42: "Status: Hardwarefehler",
        43: "Status: Fehler in der Messung",
        44: "Status: Fehler bei der Geräteinitialisierung",
        45: "Status: Fehler im Betriebssystem",
        48: "Status: Fehler in der Konfiguration, Default-Konfiguration wurde geladen",
        49: "Status: Fehler im Abgleich / der Abgleich ist ungültig, Messung nicht möglich",
        50: "Status: CRC-Fehler beim Laden der Konfiguration; Default-Konfiguration wurde geladen",
        51: "Status: CRC-Fehler beim Laden der Abgleich-Daten; Messung nicht möglich",
        52: "Status: Abgleich Step 1",
        53: "Status: Abgleich OK",
        54: "Status: Kanal deaktiviert",
    }

    def __init__(self, code: int, status_message: str):
        self.code = code
        self.status_message = status_message

    @classmethod
    def create(cls, code: int) -> "UMBStatus":
        try:
            return UMBStatus(code, UMBStatus._STATUS_CODES[code])
        except KeyError:
            raise UMBError(f"Invalid UMB status code: '{code}'")


class UMBError(Exception):
    pass


class UMB:
    """
    This is a simple driver for communicating to Weatherstations
    made by the German company Lufft. It implements their UMB-Protocol.
    You just need a USB-to-RS485 dongle and connect it to your PWS
    according to the wiring diagram you find in the manual.
    Downsides: This class does not replace the UMB-config-tool, because
    it's not able to set the config values in your PWS at the moment.

    Methods
    -------
    onlineDataQuery (channel, receiver_id=1):
        Use this method to request a value from one channel.
        It will return a (value, status) tuple.
        Status number 0 means everything is ok.
        It has more the one PWS on the BUS, use receiver_id to
        distinguish between them.

    Usage
    -----
    In your python-script:
        from WS_UMB import WS_UMB

        with WS_UMB() as umb:
            value, status = umb.onlineDataQuery(SomeChannelNumber)
            if status != 0:
                print(umb.checkStatus(status))
            else:
                print(value)
    """

    def __init__(self, serial_port: str, logger: Logger, baud_rate: int = 9600):
        self._port = serial_port
        self._serial = serial.Serial(
            baudrate=baud_rate,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            bytesize=serial.EIGHTBITS,
            timeout=0.1)
        self._serial.port = serial_port
        self._logger = logger

    def connect(self, retries: int = 0, delay: int = 2, stop_event=None) -> None:
        attempts = 0
        while retries == 0 or attempts < retries:
            if stop_event is not None and stop_event.is_set():
                return
            try:
                if self._serial.is_open:
                    self._serial.close()
                self._serial.open()
                return
            except serial.SerialException as e:
                attempts += 1
                self._logger.log(f"Attempt {attempts} failed to open port '{self._port}': {e}. "
                                 f"Retrying in {delay} seconds...")
                if stop_event is not None:
                    if stop_event.wait(delay):
                        return
                else:
                    time.sleep(delay)
        raise serial.SerialException(f"Could not open the serial port {self._port} after {retries} attempts.")

    def close(self):
        self._serial.close()

    def read_from_serial(self, timeout=0.5, inter_byte_timeout=0.1):
        end = time.monotonic() + timeout
        data = b''

        while time.monotonic() < end:
            if self._serial.in_waiting > 0:
                data += self._serial.read(self._serial.in_waiting)
                end = time.monotonic() + inter_byte_timeout
            else:
                time.sleep(0.01)
        return data

    def calc_next_crc_byte(self, crc_buff, next_byte):
        for _ in range(8):
            lsb = (crc_buff ^ next_byte) & 0x01
            crc_buff >>= 1
            next_byte >>= 1
            if lsb:
                crc_buff ^= 0x8408
        return crc_buff

    def calc_crc16(self, data):
        crc = 0xFFFF
        for byte in data:
            crc = self.calc_next_crc_byte(crc, byte)
        return crc

    def send_request(self, receiver_id, command, command_version, payload) -> Tuple[int, UMBStatus]:
        SOH, STX, ETX, EOT = b'\x01', b'\x02', b'\x03', b'\x04'
        VERSION = b'\x10'
        TO = int(receiver_id).to_bytes(1, 'little')
        TO_CLASS = b'\x70'
        FROM = int(1).to_bytes(1, 'little')
        FROM_CLASS = b'\xF0'

        LEN = len(payload) + 2
        LEN = int(LEN).to_bytes(1, 'little')

        COMMAND = int(command).to_bytes(1, 'little')
        COMMAND_VERSION = int(command_version).to_bytes(1, 'little')

        # Assemble transmit-frame
        tx_frame = SOH + VERSION + TO + TO_CLASS + FROM + FROM_CLASS + LEN + STX + COMMAND + COMMAND_VERSION + payload + ETX
        # calculate checksum for trasmit-frame and concatenate
        tx_frame += self.calc_crc16(tx_frame).to_bytes(2, 'little') + EOT

        # Write transmit-frame to serial
        self._serial.reset_input_buffer()
        self._serial.write(tx_frame)
        rx_frame = self.read_from_serial()
        if not rx_frame:
            raise UMBError("No response from wind sensor (timeout)")

        # compare checksum field to calculated checksum
        cs_calculated = self.calc_crc16(rx_frame[:-3]).to_bytes(2, 'little')
        cs_received = rx_frame[-3:-1]
        if cs_calculated != cs_received:
            raise UMBError("RX-Error! Checksum test failed. Calculated Checksum: " + str(
                cs_calculated) + "| Received Checksum: " + str(cs_received))

        # Check the length of the frame
        length = int.from_bytes(rx_frame[6:7], byteorder='little')
        if rx_frame[8 + length:9 + length] != ETX:
            raise UMBError("RX-Error! Length of Payload is not valid. length-field says: " + str(length))
        # Check if all frame field are valid
        if rx_frame[0:1] != SOH:
            raise UMBError("RX-Error! No Start-of-frame Character")
        if rx_frame[1:2] != VERSION:
            raise UMBError("RX-Error! Wrong Version Number")
        if rx_frame[2:4] != (FROM + FROM_CLASS):
            raise UMBError("RX-Error! Wrong Destination ID")
        if rx_frame[4:6] != (TO + TO_CLASS):
            raise UMBError("RX-Error! Wrong Source ID")
        if rx_frame[7:8] != STX:
            raise UMBError("RX-Error! Missing STX field")
        if rx_frame[8:9] != COMMAND:
            raise UMBError("RX-Error! Wrong Command Number")
        if rx_frame[9:10] != COMMAND_VERSION:
            raise UMBError("RX-Error! Wrong Command Version Number")

        status = int.from_bytes(rx_frame[10:11], byteorder='little')
        status_obj = UMBStatus.create(status)
        if status_obj.code != 0:
            raise UMBError(status_obj.status_message)
        value = self._get_value_from_rx_frame(rx_frame)
        return value, status_obj

    def _get_value_from_rx_frame(self, rx_frame):
        type_of_value = int.from_bytes(rx_frame[13:14], byteorder='little')
        value = 0
        if type_of_value == 16:  # UNSIGNED_CHAR
            value = struct.unpack('<B', rx_frame[14:15])[0]
        elif type_of_value == 17:  # SIGNED_CHAR
            value = struct.unpack('<b', rx_frame[14:15])[0]
        elif type_of_value == 18:  # UNSIGNED_SHORT
            value = struct.unpack('<H', rx_frame[14:16])[0]
        elif type_of_value == 19:  # SIGNED_SHORT
            value = struct.unpack('<h', rx_frame[14:16])[0]
        elif type_of_value == 20:  # UNSIGNED_LONG
            value = struct.unpack('<L', rx_frame[14:18])[0]
        elif type_of_value == 21:  # SIGNED_LONG
            value = struct.unpack('<l', rx_frame[14:18])[0]
        elif type_of_value == 22:  # FLOAT
            value = struct.unpack('<f', rx_frame[14:18])[0]
        elif type_of_value == 23:  # DOUBLE
            value = struct.unpack('<d', rx_frame[14:22])[0]
        return value

    def query_data_from_channel(self, channel, receiver_id=1):
        return self.send_request(receiver_id, 35, 16, int(channel).to_bytes(2, 'little'))

    def get_wind_measurement(self) -> WindMeasurementMessage:
        speed, status = self.query_data_from_channel(401)
        if status.code != 0:
            self._logger.log(status.status_message)

        heading, status = self.query_data_from_channel(501)
        if status.code != 0:
            self._logger.log(status.status_message)

        return WindMeasurementMessage.create(gps_time.now, speed, heading)
