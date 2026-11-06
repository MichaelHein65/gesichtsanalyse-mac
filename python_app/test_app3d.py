"""Lifecycle tests for the local 3D frontend server."""

from __future__ import annotations

import socket
import unittest
import urllib.request

from app3d import LocalAvatarServer


class LocalAvatarServerTests(unittest.TestCase):
    def test_server_stops_and_releases_its_port(self) -> None:
        server = LocalAvatarServer()
        server.start()
        port = server.port
        self.assertIsNotNone(port)

        with urllib.request.urlopen(server.url, timeout=2) as response:
            self.assertEqual(response.status, 200)
            self.assertIn(b"3D Face Studio", response.read())

        server.stop()
        with socket.socket() as probe:
            self.assertNotEqual(probe.connect_ex(("127.0.0.1", int(port))), 0)


if __name__ == "__main__":
    unittest.main()
