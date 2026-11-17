
import argparse
import socket
import time


def probe_tcp(host, port):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(3.0)
    try:
        s.connect((host, port))
        print(f"OK: TCP {host}:{port} is OPEN (something is listening).")
    except Exception as e:
        print(f"FAIL: cannot open TCP {host}:{port} -> {e}")
    finally:
        s.close()


def listen_tcp(host, port, seconds):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(1.0)
    s.connect((host, port))
    print(f"Connected to {host}:{port}. Listening {seconds}s...")
    end = time.time() + seconds
    buf = b""
    got = False
    while time.time() < end:
        try:
            chunk = s.recv(1024)
            if not chunk:
                continue
            buf += chunk
            while b"\r" in buf or b"\n" in buf:
                sep = b"\r" if b"\r" in buf else b"\n"
                line, buf = buf.split(sep, 1)
                if line.strip():
                    got = True
                    print("LINE:", repr(line.decode("utf-8", "replace")))
        except socket.timeout:
            pass
    if not got:
        print("(nothing received -> device is probably not streaming; try --cmd)")
    s.close()


def poll_tcp(host, port, cmd):
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(3.0)
    s.connect((host, port))
    s.sendall(cmd.encode() + b"\r")
    time.sleep(0.5)
    data = b""
    try:
        data = s.recv(4096)
    except socket.timeout:
        pass
    print("REPLY:", repr(data.decode("utf-8", "replace")) or "(no reply)")
    s.close()


def listen_serial(port, baud, seconds):
    import serial
    ser = serial.Serial(port, baudrate=baud, timeout=1.0)
    print(f"Opened {port} @ {baud}. Listening {seconds}s...")
    end = time.time() + seconds
    got = False
    while time.time() < end:
        line = ser.readline()
        if line.strip():
            got = True
            print("LINE:", repr(line.decode("utf-8", "replace")))
    if not got:
        print("(nothing received on serial)")
    ser.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--tcp", help="host:port")
    ap.add_argument("--serial", help="/dev/ttyUSB0")
    ap.add_argument("--baud", type=int, default=9600)
    ap.add_argument("--listen", type=int, default=0, help="seconds to listen")
    ap.add_argument("--cmd", help="poll command to send (TCP)")
    ap.add_argument("--probe", action="store_true", help="just test if TCP port is open")
    args = ap.parse_args()

    if args.tcp and args.probe:
        host, port = args.tcp.split(":")
        probe_tcp(host, int(port))
    elif args.tcp and args.cmd:
        host, port = args.tcp.split(":")
        poll_tcp(host, int(port), args.cmd)
    elif args.tcp:
        host, port = args.tcp.split(":")
        listen_tcp(host, int(port), args.listen or 10)
    elif args.serial:
        listen_serial(args.serial, args.baud, args.listen or 10)
    else:
        ap.print_help()
