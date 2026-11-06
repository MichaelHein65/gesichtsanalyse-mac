"""Native macOS window for the MediaPipe-driven Three.js avatar."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import threading
import time
from pathlib import Path
from typing import Any

import cv2
import mediapipe as mp
import numpy as np
import objc
import webview
from aiohttp import web
from AppKit import NSApplication
from Foundation import NSDate, NSBundle, NSRunLoop

from face_analysis import (
    ExponentialSmoother,
    HeadPose,
    JsonlRecorder,
    categories_to_dict,
    rotation_matrix_to_head_pose,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MODEL_PATH = PROJECT_ROOT / "models" / "face_landmarker.task"
WEB_ROOT = PROJECT_ROOT / "web3d"
OUTPUT_DIRECTORY = PROJECT_ROOT / "output"


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="3D-Avatar mit MediaPipe-Steuerung")
    parser.add_argument("camera", type=int, nargs="?", default=0)
    return parser.parse_args()


def create_landmarker() -> mp.tasks.vision.FaceLandmarker:
    if not MODEL_PATH.is_file():
        raise FileNotFoundError(f"MediaPipe-Modell fehlt: {MODEL_PATH}")
    options = mp.tasks.vision.FaceLandmarkerOptions(
        base_options=mp.tasks.BaseOptions(
            model_asset_path=str(MODEL_PATH),
            delegate=mp.tasks.BaseOptions.Delegate.CPU,
        ),
        running_mode=mp.tasks.vision.RunningMode.VIDEO,
        num_faces=1,
        min_face_detection_confidence=0.5,
        min_face_presence_confidence=0.5,
        min_tracking_confidence=0.5,
        output_face_blendshapes=True,
        output_facial_transformation_matrixes=True,
    )
    return mp.tasks.vision.FaceLandmarker.create_from_options(options)


def open_camera(index: int) -> cv2.VideoCapture:
    camera = cv2.VideoCapture(index, cv2.CAP_AVFOUNDATION)
    if not camera.isOpened():
        camera.release()
        camera = cv2.VideoCapture(index)
    if not camera.isOpened():
        raise RuntimeError(
            f"Kamera {index} konnte nicht geöffnet werden. Prüfe die Kamerafreigabe."
        )
    camera.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    camera.set(cv2.CAP_PROP_FPS, 30)
    return camera


def request_camera_permission() -> bool:
    """Ask through the real app bundle before OpenCV touches AVFoundation."""

    NSApplication.sharedApplication()
    framework = NSBundle.bundleWithPath_(
        "/System/Library/Frameworks/AVFoundation.framework"
    )
    if framework is None or not framework.load():
        return False

    capture_device = objc.lookUpClass("AVCaptureDevice")
    video_media_type = "vide"
    status = int(capture_device.authorizationStatusForMediaType_(video_media_type))
    if status == 3:  # AVAuthorizationStatusAuthorized
        return True
    if status in (1, 2):  # restricted or denied
        return False

    finished = threading.Event()
    granted = False

    def permission_result(is_granted: bool) -> None:
        nonlocal granted
        granted = bool(is_granted)
        finished.set()

    capture_device.requestAccessForMediaType_completionHandler_(
        video_media_type, permission_result
    )
    run_loop = NSRunLoop.currentRunLoop()
    while not finished.is_set():
        run_loop.runUntilDate_(NSDate.dateWithTimeIntervalSinceNow_(0.05))
    return granted


class LocalAvatarServer:
    """Serves the bundled UI and broadcasts tracking frames over a local socket."""

    def __init__(self) -> None:
        self.loop: asyncio.AbstractEventLoop | None = None
        self.port: int | None = None
        self._clients: set[web.WebSocketResponse] = set()
        self._ready = threading.Event()
        self._thread: threading.Thread | None = None
        self._stop_event: asyncio.Event | None = None
        self._startup_error: BaseException | None = None
        self._last_payload: dict[str, Any] = {"type": "ready", "face": False}

    @property
    def url(self) -> str:
        if self.port is None:
            raise RuntimeError("Server ist noch nicht gestartet")
        return f"http://127.0.0.1:{self.port}/"

    def start(self) -> None:
        self._thread = threading.Thread(
            target=self._thread_main, name="avatar-web-server", daemon=True
        )
        self._thread.start()
        if not self._ready.wait(timeout=10):
            raise RuntimeError("Der lokale Avatar-Server antwortet nicht.")
        if self._startup_error is not None:
            raise RuntimeError("Der lokale Avatar-Server konnte nicht starten.") from self._startup_error

    def _thread_main(self) -> None:
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        try:
            self.loop.run_until_complete(self._serve())
        except BaseException as error:  # surfaced on the UI thread
            self._startup_error = error
            self._ready.set()
        finally:
            self.loop.close()

    async def _serve(self) -> None:
        self._stop_event = asyncio.Event()
        app = web.Application()
        app.router.add_get("/", self._index)
        app.router.add_get("/ws", self._websocket)
        app.router.add_static("/assets/", WEB_ROOT / "assets", show_index=False)
        app.router.add_static("/vendor/", WEB_ROOT / "vendor", show_index=False)

        runner = web.AppRunner(app, access_log=None)
        await runner.setup()
        site = web.TCPSite(runner, "127.0.0.1", 0)
        await site.start()
        sockets = getattr(site._server, "sockets", None)  # aiohttp has no public port API
        if not sockets:
            raise RuntimeError("Kein lokaler Port verfügbar")
        self.port = int(sockets[0].getsockname()[1])
        self._ready.set()
        await self._stop_event.wait()
        for client in tuple(self._clients):
            await client.close(code=1001, message=b"App closed")
        await runner.cleanup()

    async def _index(self, _request: web.Request) -> web.FileResponse:
        return web.FileResponse(WEB_ROOT / "index.html")

    async def _websocket(self, request: web.Request) -> web.WebSocketResponse:
        socket = web.WebSocketResponse(heartbeat=15)
        await socket.prepare(request)
        self._clients.add(socket)
        try:
            await socket.send_json(self._last_payload)
            async for _message in socket:
                pass
        finally:
            self._clients.discard(socket)
        return socket

    async def _broadcast(self, message: str) -> None:
        if not self._clients:
            return
        clients = tuple(self._clients)
        results = await asyncio.gather(
            *(client.send_str(message) for client in clients),
            return_exceptions=True,
        )
        for client, result in zip(clients, results):
            if isinstance(result, BaseException):
                self._clients.discard(client)

    def broadcast(self, payload: dict[str, Any]) -> None:
        self._last_payload = payload
        if self.loop is None or not self.loop.is_running():
            return
        message = json.dumps(payload, separators=(",", ":"))
        asyncio.run_coroutine_threadsafe(self._broadcast(message), self.loop)

    def stop(self) -> None:
        if self.loop is not None and self._stop_event is not None:
            self.loop.call_soon_threadsafe(self._stop_event.set)
        if self._thread is not None:
            self._thread.join(timeout=5)


class FaceTracker:
    """Owns camera, MediaPipe and the optional JSONL recording."""

    def __init__(
        self,
        camera_index: int,
        server: LocalAvatarServer,
        camera: cv2.VideoCapture | None,
        camera_error: BaseException | None = None,
    ) -> None:
        self.camera_index = camera_index
        self.server = server
        self.camera = camera
        self.camera_error = camera_error
        self.recorder = JsonlRecorder(OUTPUT_DIRECTORY)
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._record_lock = threading.Lock()

    def start(self) -> None:
        self._thread = threading.Thread(
            target=self._run, name="face-tracker", daemon=True
        )
        self._thread.start()

    def toggle_recording(self) -> dict[str, Any]:
        with self._record_lock:
            path = self.recorder.toggle()
            return {
                "active": self.recorder.active,
                "path": str(path) if path else None,
            }

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=5)
        with self._record_lock:
            self.recorder.close()

    def _run(self) -> None:
        camera = self.camera
        landmarker: mp.tasks.vision.FaceLandmarker | None = None
        smoother = ExponentialSmoother(alpha=0.42)
        start = time.monotonic()
        previous = start
        fps = 0.0
        try:
            if camera is None:
                raise self.camera_error or RuntimeError(
                    f"Kamera {self.camera_index} konnte nicht geöffnet werden."
                )
            landmarker = create_landmarker()
            while not self._stop.is_set():
                ok, frame = camera.read()
                if not ok:
                    raise RuntimeError("Kein Kamerabild empfangen.")
                frame = cv2.flip(frame, 1)
                width = min(frame.shape[1], 640)
                height = round(frame.shape[0] * width / frame.shape[1])
                frame = cv2.resize(frame, (width, height), interpolation=cv2.INTER_AREA)
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                timestamp_ms = int((time.monotonic() - start) * 1000)
                result = landmarker.detect_for_video(
                    mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb),
                    timestamp_ms,
                )

                now = time.monotonic()
                instantaneous = 1.0 / max(now - previous, 1e-6)
                fps = instantaneous if fps == 0.0 else fps * 0.9 + instantaneous * 0.1
                previous = now

                if not result.face_landmarks:
                    smoother.reset()
                    self.server.broadcast(
                        {"type": "tracking", "face": False, "fps": round(fps, 1)}
                    )
                    continue

                landmarks = smoother.landmarks(
                    np.array(
                        [[point.x, point.y, point.z] for point in result.face_landmarks[0]],
                        dtype=np.float64,
                    )
                )
                pose: HeadPose | None = None
                if result.facial_transformation_matrixes:
                    pose = smoother.pose(
                        rotation_matrix_to_head_pose(
                            result.facial_transformation_matrixes[0]
                        )
                    )
                blendshapes: dict[str, float] = {}
                if result.face_blendshapes:
                    blendshapes = smoother.blendshapes(
                        categories_to_dict(result.face_blendshapes[0])
                    )

                if pose is not None:
                    with self._record_lock:
                        self.recorder.write(
                            timestamp_ms, pose, blendshapes, landmarks
                        )

                self.server.broadcast(
                    {
                        "type": "tracking",
                        "face": True,
                        "fps": round(fps, 1),
                        "pose": {
                            "yaw": round(pose.yaw, 3) if pose else 0.0,
                            "pitch": round(pose.pitch, 3) if pose else 0.0,
                            "roll": round(pose.roll, 3) if pose else 0.0,
                        },
                        "blendshapes": blendshapes,
                    }
                )
        except BaseException as error:
            self.server.broadcast(
                {"type": "error", "message": str(error), "face": False}
            )
        finally:
            if landmarker is not None:
                landmarker.close()
            if camera is not None:
                camera.release()


class AppApi:
    """Small native bridge used by the two title-bar buttons."""

    def __init__(self, tracker: FaceTracker) -> None:
        self.tracker = tracker
        self.window: webview.Window | None = None

    def toggle_recording(self) -> dict[str, Any]:
        return self.tracker.toggle_recording()

    def close(self) -> None:
        if self.window is not None:
            self.window.destroy()


def main() -> None:
    arguments = parse_arguments()
    if not (WEB_ROOT / "vendor" / "three.module.js").is_file():
        raise FileNotFoundError(
            "Three.js fehlt. Bitte setup_python.command erneut ausführen."
        )

    server = LocalAvatarServer()
    server.start()
    camera: cv2.VideoCapture | None = None
    camera_error: BaseException | None = None
    try:
        # AVFoundation must ask for first-time camera permission on the main thread.
        if not request_camera_permission():
            raise PermissionError(
                "Kamerazugriff fehlt. Bitte in Systemeinstellungen > Datenschutz & "
                "Sicherheit > Kamera für Gesichtsanalyse aktivieren."
            )
        camera = open_camera(arguments.camera)
    except BaseException as error:
        camera_error = error
    tracker = FaceTracker(arguments.camera, server, camera, camera_error)
    api = AppApi(tracker)
    tracker.start()
    try:
        api.window = webview.create_window(
            "Mimic – 3D Gesicht",
            server.url,
            js_api=api,
            width=1280,
            height=820,
            min_size=(900, 620),
            background_color="#140d25",
        )
        webview.start(debug=False, private_mode=False)
    finally:
        tracker.stop()
        server.stop()


if __name__ == "__main__":
    exit_status = 0
    try:
        main()
    except BaseException as error:
        print(f"Anwendungsfehler: {error}", file=sys.stderr, flush=True)
        exit_status = 1
    finally:
        # Cocoa can retain framework threads after the last pywebview window closes.
        # At this point camera, tracker and local server have already been stopped.
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(exit_status)
