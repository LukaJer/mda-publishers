import socket
import time
from abc import ABC, abstractmethod

import serial

from publishers.logger import Logger


class ConnectionStrategy(ABC):
    TERMINATION_CHARACTER = b'\r'

    @abstractmethod
    def connect(self, retries: int = 0, delay: int = 2) -> None:
        pass

    @abstractmethod
    def write(self, cmd: str) -> None:
        pass

    @abstractmethod
    def read(self) -> bytes:
        pass

    @abstractmethod
    def close(self) -> None:
        pass


class SerialConnectionStrategy(ConnectionStrategy):
    def __init__(self, port: str, logger: Logger = None) -> None:
        self._port = port
        self._logger = logger
        self.serial = serial.Serial()
        self.serial.port = port

    def connect(self, retries: int = 0, delay: int = 2) -> None:
        attempts = 0
        while retries == 0 or attempts < retries:
            try:
                self.serial.open()
                return
            except serial.SerialException as e:
                attempts += 1
                self._logger.log(f"Attempt {attempts} failed to open port '{self._port}': {e}. "
                                 f"Retrying in {delay} seconds...")
                time.sleep(delay)
        raise serial.SerialException(f"Could not open the serial port {self._port} after {retries} attempts.")

    def write(self, cmd: str) -> None:
        self.serial.write(cmd.encode() + self.TERMINATION_CHARACTER)

    def read(self) -> bytes:
        buffer = b""
        while True:
            c = self.serial.read(1)
            if c == self.TERMINATION_CHARACTER:
                break
            buffer += c
        return buffer

    def close(self) -> None:
        self.serial.close()


class TcpConnectionStrategy(ConnectionStrategy):
    def __init__(self, host: str, port: int, logger: Logger = None) -> None:
        self._host = host
        self._port = port
        self._logger = logger
        self._tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    def connect(self, retries: int = 0, delay: int = 2) -> None:
        attempts = 0
        while retries == 0 or attempts < retries:
            try:
                self._tcp_socket.connect((self._host, self._port))
                return
            except Exception as e:
                attempts += 1
                self._logger.log(f"Attempt {attempts} failed to connect to host '{self._host}:{self._port}': {e}. "
                                    f"Retrying in {delay} seconds...")
                time.sleep(delay)
        raise Exception(f"Could not establish connection to host {self._host} on port {self._port}.")

    def write(self, cmd: str) -> None:
        self._tcp_socket.sendall(cmd.encode() + self.TERMINATION_CHARACTER)

    def read(self) -> bytes:
        buffer = b""
        while True:
            c = self._tcp_socket.recv(1)
            if c == self.TERMINATION_CHARACTER:
                break
            buffer += c
        return buffer

    def close(self) -> None:
        self._tcp_socket.close()