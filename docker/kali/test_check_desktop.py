import socket
import struct
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from check_desktop import check_desktop, receive


class DesktopHealthTests(unittest.TestCase):
    def test_probe_completes_shared_handshake_with_fragmented_server_messages(self):
        client, server = socket.socketpair()
        client.settimeout(2)
        server.settimeout(2)

        def serve():
            with server:
                server.sendall(b"RFB 003.")
                server.sendall(b"008\n")
                self.assertEqual(receive(server, 12), b"RFB 003.008\n")
                server.sendall(b"\x01\x01")
                self.assertEqual(receive(server, 1), b"\x01")
                server.sendall(b"\x00\x00\x00\x00")
                # Exclusive probes would kick the user out every five seconds.
                self.assertEqual(receive(server, 1), b"\x01")
                server.sendall(struct.pack(">HH", 1440, 900) + bytes(16) + struct.pack(">I", 4))
                server.sendall(b"Kali")
                self.assertEqual(server.recv(1), b"")

        with ThreadPoolExecutor(max_workers=1) as pool:
            result = pool.submit(serve)
            with patch("check_desktop.socket.create_connection", return_value=client):
                check_desktop()
            result.result(timeout=3)

    def test_blacklist_banner_is_not_healthy(self):
        client, server = socket.socketpair()
        with server:
            server.sendall(b"RFB 003.003\n")
            with patch("check_desktop.socket.create_connection", return_value=client):
                with self.assertRaises(OSError):
                    check_desktop()

    def test_truncated_banner_is_not_healthy(self):
        client, server = socket.socketpair()
        server.sendall(b"RFB ")
        server.close()
        with patch("check_desktop.socket.create_connection", return_value=client):
            with self.assertRaises(OSError):
                check_desktop()


if __name__ == "__main__":
    unittest.main()
