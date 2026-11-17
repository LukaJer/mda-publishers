import socket
import struct

from publishers.gps_time import gps_time


class SimpleNTPServer:
    NTP_EPOCH = 2208988800  # NTP epoch starts from 1900, UNIX from 1970

    def __init__(self, ntp_port=1123):
        self.ntp_port = ntp_port

    def get_gps_time(self):
        """
        Retrieves the current time from the GPS receiver using the gps_time.now() method.
        Converts the datetime object to a UNIX timestamp.
        """
        try:
            unix_timestamp = gps_time.now().timestamp()
            return unix_timestamp
        except Exception as e:
            print(f"Error retrieving GPS time: {e}")
            return None

    def ntp_packet(self, transmit_timestamp):
        """
        Constructs an NTP packet based on the transmit timestamp.
        """
        # Convert UNIX time to NTP time
        transmit_time = int(transmit_timestamp + self.NTP_EPOCH)
        fraction = int((transmit_timestamp - int(transmit_timestamp)) * 2**32)

        # NTP packet structure (with minimal required fields set):
        packet = b'\x1b' + 47 * b'\0'  # NTP mode 4 (server mode)
        packet = struct.pack('!B B B B 11I', 0x1b, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, transmit_time, fraction)

        return packet

    def serve_ntp(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind(('', self.ntp_port))

        print("NTP server running...")

        while True:
            try:
                # Wait for a client request
                data, address = sock.recvfrom(1024)
                gps_time = self.get_gps_time()
                if gps_time:
                    # Construct and send an NTP response
                    response = self.ntp_packet(gps_time)
                    sock.sendto(response, address)
            except KeyboardInterrupt:
                print("Shutting down the NTP server.")
                break
            except Exception as e:
                print(f"Error: {e}")


if __name__ == "__main__":
    ntp_server = SimpleNTPServer()
    ntp_server.serve_ntp()
