"""Echtzeit-Face-Mesh, Kopfpose und Mimik mit MediaPipe und OpenCV."""

from __future__ import annotations

import argparse
import time
from pathlib import Path

import cv2
import mediapipe as mp
import numpy as np

from avatar import render_avatar
from face_analysis import (
    ExponentialSmoother,
    HeadPose,
    JsonlRecorder,
    categories_to_dict,
    rotation_matrix_to_head_pose,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MODEL_PATH = PROJECT_ROOT / "models" / "face_landmarker.task"
OUTPUT_DIRECTORY = PROJECT_ROOT / "output"
WINDOW_TITLE = "Gesichtsanalyse – A: Kamera/Avatar, R: Aufnahme, Q: Ende"
PANEL_WIDTH = 390

MESH_COLOR = (90, 170, 255)
CONTOUR_COLOR = (90, 240, 120)
EYE_COLOR = (255, 190, 70)
LIP_COLOR = (120, 120, 255)
TEXT_COLOR = (235, 238, 244)
MUTED_COLOR = (160, 168, 180)
ACCENT_COLOR = (80, 220, 255)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="MediaPipe Face Mesh mit Kopfpose und Blendshapes"
    )
    parser.add_argument(
        "camera",
        type=int,
        nargs="?",
        default=0,
        help="Kameraindex, standardmäßig 0",
    )
    parser.add_argument(
        "--avatar",
        action="store_true",
        help="Anwendung direkt in der Avataransicht starten",
    )
    return parser.parse_args()


def create_landmarker() -> mp.tasks.vision.FaceLandmarker:
    if not MODEL_PATH.is_file():
        raise FileNotFoundError(
            f"MediaPipe-Modell fehlt: {MODEL_PATH}\n"
            "Bitte `./setup_python.command` ausführen."
        )

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


def landmark_array(face_landmarks: list[object]) -> np.ndarray:
    return np.array(
        [[landmark.x, landmark.y, landmark.z] for landmark in face_landmarks],
        dtype=np.float64,
    )


def pixel_point(point: np.ndarray, width: int, height: int) -> tuple[int, int]:
    return (
        max(0, min(width - 1, int(point[0] * width))),
        max(0, min(height - 1, int(point[1] * height))),
    )


def draw_connections(
    image: np.ndarray,
    landmarks: np.ndarray,
    connections: list[object],
    color: tuple[int, int, int],
    thickness: int = 1,
) -> None:
    height, width = image.shape[:2]
    for connection in connections:
        start = pixel_point(landmarks[connection.start], width, height)
        end = pixel_point(landmarks[connection.end], width, height)
        cv2.line(image, start, end, color, thickness, cv2.LINE_AA)


def draw_face_mesh(image: np.ndarray, landmarks: np.ndarray) -> None:
    connections = mp.tasks.vision.FaceLandmarksConnections
    draw_connections(
        image,
        landmarks,
        connections.FACE_LANDMARKS_TESSELATION,
        MESH_COLOR,
    )
    draw_connections(
        image,
        landmarks,
        connections.FACE_LANDMARKS_FACE_OVAL,
        CONTOUR_COLOR,
        2,
    )
    for region in (
        connections.FACE_LANDMARKS_LEFT_EYE,
        connections.FACE_LANDMARKS_RIGHT_EYE,
        connections.FACE_LANDMARKS_LEFT_IRIS,
        connections.FACE_LANDMARKS_RIGHT_IRIS,
        connections.FACE_LANDMARKS_LEFT_EYEBROW,
        connections.FACE_LANDMARKS_RIGHT_EYEBROW,
    ):
        draw_connections(image, landmarks, region, EYE_COLOR, 2)
    draw_connections(
        image, landmarks, connections.FACE_LANDMARKS_LIPS, LIP_COLOR, 2
    )


def put_text(
    image: np.ndarray,
    text: str,
    x: int,
    y: int,
    color: tuple[int, int, int] = TEXT_COLOR,
    scale: float = 0.55,
    thickness: int = 1,
) -> None:
    cv2.putText(
        image,
        text,
        (x, y),
        cv2.FONT_HERSHEY_SIMPLEX,
        scale,
        color,
        thickness,
        cv2.LINE_AA,
    )


def top_blendshapes(values: dict[str, float], limit: int = 12) -> list[tuple[str, float]]:
    filtered = ((name, score) for name, score in values.items() if name != "_neutral")
    return sorted(filtered, key=lambda item: item[1], reverse=True)[:limit]


def draw_panel(
    frame: np.ndarray,
    pose: HeadPose | None,
    blendshapes: dict[str, float],
    recording: bool,
    fps: float,
    avatar_mode: bool,
) -> np.ndarray:
    height, width = frame.shape[:2]
    canvas = np.zeros((height, width + PANEL_WIDTH, 3), dtype=np.uint8)
    canvas[:, :width] = frame
    canvas[:, width:] = (25, 29, 38)
    x = width + 22

    mode_name = "AVATAR" if avatar_mode else "FACE MESH"
    put_text(canvas, mode_name, x, 34, ACCENT_COLOR, 0.65, 2)
    put_text(canvas, f"{fps:4.1f} FPS", x + 250, 34, MUTED_COLOR, 0.48)

    if pose is None:
        put_text(canvas, "Kein Gesicht erkannt", x, 76, (90, 170, 255), 0.62, 2)
    else:
        put_text(canvas, "KOPFRICHTUNG", x, 76, MUTED_COLOR, 0.48, 1)
        put_text(canvas, f"Yaw    {pose.yaw:7.2f} Grad", x, 105)
        put_text(canvas, f"Pitch  {pose.pitch:7.2f} Grad", x, 132)
        put_text(canvas, f"Roll   {pose.roll:7.2f} Grad", x, 159)

        put_text(canvas, "STAERKSTE MIMIKWERTE", x, 202, MUTED_COLOR, 0.48, 1)
        y = 230
        for name, value in top_blendshapes(blendshapes):
            put_text(canvas, f"{name[:25]:25s} {value:0.3f}", x, y, TEXT_COLOR, 0.46)
            bar_width = int(np.clip(value, 0.0, 1.0) * 100)
            cv2.rectangle(canvas, (x + 235, y - 11), (x + 235 + bar_width, y - 4), ACCENT_COLOR, -1)
            y += 25

    put_text(canvas, "A  Kamera / Avatar", x, height - 84, MUTED_COLOR, 0.48)
    status_color = (80, 80, 255) if recording else MUTED_COLOR
    status = "AUFNAHME AKTIV" if recording else "R  Aufnahme starten"
    put_text(canvas, status, x, height - 55, status_color, 0.52, 2 if recording else 1)
    put_text(canvas, "Q / Esc  Beenden", x, height - 26, MUTED_COLOR, 0.48)
    return canvas


def main() -> None:
    arguments = parse_arguments()
    camera = open_camera(arguments.camera)
    landmarker = create_landmarker()
    smoother = ExponentialSmoother(alpha=0.48)
    recorder = JsonlRecorder(OUTPUT_DIRECTORY)
    start = time.monotonic()
    previous_frame_time = start
    fps = 0.0
    face_was_detected: bool | None = None
    avatar_mode = arguments.avatar

    print(f"Kamera {arguments.camera} geöffnet.")
    print("A: Kamera/Avatar | R: Aufnahme starten/stoppen | Q oder Esc: beenden")
    print(f"Ansicht: {'Avatar' if avatar_mode else 'Face Mesh'}")

    try:
        while True:
            ok, frame = camera.read()
            if not ok:
                raise RuntimeError("Kein Kamerabild empfangen.")

            frame = cv2.flip(frame, 1)
            analysis_width = min(frame.shape[1], 640)
            analysis_height = round(frame.shape[0] * analysis_width / frame.shape[1])
            analysis_frame = cv2.resize(
                frame, (analysis_width, analysis_height), interpolation=cv2.INTER_AREA
            )
            rgb = cv2.cvtColor(analysis_frame, cv2.COLOR_BGR2RGB)
            timestamp_ms = int((time.monotonic() - start) * 1000)
            mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            result = landmarker.detect_for_video(mp_image, timestamp_ms)

            pose: HeadPose | None = None
            blendshapes: dict[str, float] = {}
            landmarks: np.ndarray | None = None

            if result.face_landmarks:
                landmarks = smoother.landmarks(landmark_array(result.face_landmarks[0]))

                if result.facial_transformation_matrixes:
                    raw_pose = rotation_matrix_to_head_pose(
                        result.facial_transformation_matrixes[0]
                    )
                    pose = smoother.pose(raw_pose)

                if result.face_blendshapes:
                    blendshapes = smoother.blendshapes(
                        categories_to_dict(result.face_blendshapes[0])
                    )

                if not avatar_mode:
                    draw_face_mesh(frame, landmarks)

                if recorder.active and pose is not None:
                    recorder.write(timestamp_ms, pose, blendshapes, landmarks)

                if face_was_detected is not True:
                    print(
                        "Gesicht erkannt: "
                        f"{len(landmarks)} Landmarks, "
                        f"{len(blendshapes)} Blendshapes."
                    )
                face_was_detected = True
            else:
                smoother.reset()
                if face_was_detected is True:
                    print("Gesicht nicht mehr erkannt.")
                face_was_detected = False

            now = time.monotonic()
            instantaneous_fps = 1.0 / max(now - previous_frame_time, 1e-6)
            fps = instantaneous_fps if fps == 0.0 else fps * 0.9 + instantaneous_fps * 0.1
            previous_frame_time = now

            display_frame = (
                render_avatar(frame.shape[1], frame.shape[0], pose, blendshapes)
                if avatar_mode
                else frame
            )
            canvas = draw_panel(
                display_frame,
                pose,
                blendshapes,
                recorder.active,
                fps,
                avatar_mode,
            )
            cv2.imshow(WINDOW_TITLE, canvas)
            key = cv2.waitKey(1) & 0xFF
            if key in (27, ord("q"), ord("Q")):
                break
            if key in (ord("r"), ord("R")):
                path = recorder.toggle()
                state = "gestartet" if recorder.active else "beendet"
                print(f"Aufnahme {state}: {path}")
            if key in (ord("a"), ord("A")):
                avatar_mode = not avatar_mode
                mode_name = "Avatar" if avatar_mode else "Face Mesh"
                print(f"Ansicht: {mode_name}")

            if cv2.getWindowProperty(WINDOW_TITLE, cv2.WND_PROP_VISIBLE) < 1:
                break
    finally:
        recorder.close()
        landmarker.close()
        camera.release()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
