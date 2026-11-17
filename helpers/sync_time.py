import logging
import logging.handlers
import socket
import struct
import time

from windows_time_helper import WindowsTimeHelper


class TimeSync(object):
    NTP_SERVER = "pool.ntp.org"
    NTP_REQUEST_PACKET = b'\x1b' + 47 * b'\0'  # NTP request packet
    NTP_TO_UNIX_EPOCH_OFFSET = 2208988800  # Difference between NTP and UNIX epochs in seconds

    def __init__(self, ntp_port=123):
        self._ntp_port = ntp_port
        logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s', datefmt='%Y%m%d %H:%M:%S')
        handler = logging.handlers.RotatingFileHandler("log.txt", maxBytes=65536, backupCount=10)
        handler.setFormatter(logging.Formatter(fmt='%(asctime)s %(message)s', datefmt='%Y%m%d %H:%M:%S'))
        logging.getLogger('').addHandler(handler)

    def sync(self):
        round_trip_delay, clock_offset = self.get_ntp_time(self.NTP_SERVER)
        logging.info('%s: round_trip_delay=%.3f clock_offset=%.3f' % (self.NTP_SERVER, round_trip_delay, clock_offset))
        logging.info("Clock offset = %.3f s" % offset)
        r = WindowsTimeHelper.set_system_file_time(WindowsTimeHelper.get_system_file_time() + int(offset * 10000000))  # 100 nanosecond units (since 16010101)
        logging.info("Clock adjustment %s" % (r and 'carried out' or 'failed (Must run as administrator)'))

    def ntp_timestamp_to_unix_time(self, ntp_timestamp):
        seconds, fraction = ntp_timestamp
        fractional_seconds = float(fraction) / 2 ** 32
        unix_timestamp = seconds - self.NTP_TO_UNIX_EPOCH_OFFSET + fractional_seconds
        return unix_timestamp

    def get_ntp_time(self, ntp_server):
        try:
            client_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            client_socket.settimeout(0.5)

            time_before_request = time.time()

            client_socket.sendto(self.NTP_REQUEST_PACKET, (ntp_server, self._ntp_port))
            response_data, server_address = client_socket.recvfrom(1024)

            time_after_response = time.time()

            unpacked_data = struct.unpack('!12I', response_data)

            server_receive_time = self.ntp_timestamp_to_unix_time(unpacked_data[8:10])
            server_transmit_time = self.ntp_timestamp_to_unix_time(unpacked_data[10:12])

            round_trip_delay = (time_after_response - time_before_request) - (server_transmit_time - server_receive_time)
            clock_offset = ((server_receive_time - time_before_request) + (server_transmit_time - time_after_response)) / 2

            return round_trip_delay, clock_offset

        except Exception as e:
            # If there's an error (e.g., timeout), return None values
            return None, None


if __name__ == "__main__":
    t = TimeSync(1123)
    # t.sync()
    server = "localhost"
    delay, offset = t.get_ntp_time(server)
    print(offset)
