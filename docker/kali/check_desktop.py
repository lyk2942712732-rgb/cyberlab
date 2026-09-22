"""Probe VNC with a complete shared handshake, avoiding failed-auth bans."""
import socket
import struct
import time
import sys
from check_x11 import check_shell_ready


def receive(sock, length):
    data = bytearray()
    while len(data) < length:
        chunk = sock.recv(length - len(data))
        if not chunk:
            raise OSError("VNC closed during handshake")
        data.extend(chunk)
    return bytes(data)


def check_desktop(host="127.0.0.1", port=5901):
    with socket.create_connection((host, port), timeout=5) as sock:
        if receive(sock, 12) != b"RFB 003.008\n":
            raise OSError("Expected VNC protocol 3.8")
        sock.sendall(b"RFB 003.008\n")
        count = receive(sock, 1)[0]
        if not count or 1 not in receive(sock, count):
            raise OSError("VNC does not offer the configured security type")
        sock.sendall(b"\x01")  # SecurityTypes None; loopback only.
        if receive(sock, 4) != b"\x00\x00\x00\x00":
            raise OSError("VNC handshake rejected")
        sock.sendall(b"\x01")  # Shared: never disconnect a student's desktop.
        header = receive(sock, 24)
        name_length = struct.unpack(">I", header[20:24])[0]
        if name_length > 65536:
            raise OSError("Invalid VNC desktop name length")
        receive(sock, name_length)


if __name__ == "__main__":
    attempts = 100 if "--wait" in sys.argv else 1
    for attempt in range(attempts):
        try:
            check_desktop()
            # The entrypoint only waits for X/VNC before launching XFCE.
            # Docker health must additionally wait for the usable desktop.
            if "--wait" not in sys.argv:
                check_shell_ready()
            break
        except OSError:
            if attempt == attempts - 1:
                raise
            time.sleep(0.1)
