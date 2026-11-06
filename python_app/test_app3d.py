"""Lifecycle tests for the local 3D frontend server."""

from __future__ import annotations

import socket
import unittest
import urllib.request

import objc
from Foundation import NSBundle

from app3d import CAMERA_PERMISSION_METADATA, LocalAvatarServer


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


class CameraPermissionTests(unittest.TestCase):
    def test_permission_callback_declares_boolean_block_signature(self) -> None:
        callback = CAMERA_PERMISSION_METADATA["arguments"][3]["callable"]
        self.assertEqual(callback["retval"]["type"], b"v")
        self.assertEqual(callback["arguments"][0]["type"], b"^v")
        self.assertEqual(callback["arguments"][1]["type"], b"Z")

    def test_permission_selector_accepts_registered_block(self) -> None:
        framework = NSBundle.bundleWithPath_(
            "/System/Library/Frameworks/AVFoundation.framework"
        )
        self.assertIsNotNone(framework)
        self.assertTrue(framework.load())
        objc.registerMetaDataForSelector(
            b"AVCaptureDevice",
            b"requestAccessForMediaType:completionHandler:",
            CAMERA_PERMISSION_METADATA,
        )
        capture_device = objc.lookUpClass("AVCaptureDevice")
        metadata = (
            capture_device.requestAccessForMediaType_completionHandler_.__metadata__()
        )
        self.assertIn("callable", metadata["arguments"][3])


if __name__ == "__main__":
    unittest.main()
