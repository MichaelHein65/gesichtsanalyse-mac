"""Lifecycle tests for the local 3D frontend server."""

from __future__ import annotations

import json
import socket
import tempfile
import unittest
import urllib.request
from pathlib import Path

import objc
from Foundation import NSBundle

from app3d import (
    CAMERA_PERMISSION_METADATA,
    LocalAvatarServer,
    list_recordings,
    load_recording,
)


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

    def test_recording_api_strips_landmarks_and_normalizes_time(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            directory = Path(temporary_directory)
            path = directory / "gesicht_20261106_120000.jsonl"
            records = [
                {
                    "timestamp_ms": timestamp,
                    "head_pose_degrees": {"yaw": 2, "pitch": 3, "roll": 4},
                    "blendshapes": {"jawOpen": value},
                    "landmarks": [{"index": 0, "x": 0.5, "y": 0.5, "z": 0}],
                }
                for timestamp, value in ((5000, 0.1), (5120, 0.7))
            ]
            path.write_text(
                "".join(json.dumps(record) + "\n" for record in records),
                encoding="utf-8",
            )

            server = LocalAvatarServer(directory)
            server.start()
            try:
                with urllib.request.urlopen(
                    f"{server.url}api/recordings", timeout=2
                ) as response:
                    index = json.load(response)
                self.assertEqual(index["recordings"][0]["name"], path.name)
                with urllib.request.urlopen(
                    f"{server.url}api/recordings/{path.name}", timeout=2
                ) as response:
                    recording = json.load(response)
            finally:
                server.stop()

            self.assertEqual(recording["duration_ms"], 120)
            self.assertEqual(recording["frame_count"], 2)
            self.assertEqual(recording["frames"][0]["time_ms"], 0)
            self.assertNotIn("landmarks", recording["frames"][0])


class RecordingLoaderTests(unittest.TestCase):
    def test_recording_name_cannot_escape_output_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            with self.assertRaises(ValueError):
                load_recording(Path(temporary_directory), "../private.jsonl")

    def test_missing_recording_directory_has_empty_index(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            missing = Path(temporary_directory) / "missing"
            self.assertEqual(list_recordings(missing), [])


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
