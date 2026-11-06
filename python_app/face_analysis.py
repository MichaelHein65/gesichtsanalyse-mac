"""Auswertung und Speicherung der MediaPipe-Gesichtsdaten."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

import numpy as np


@dataclass(frozen=True)
class HeadPose:
    """Kopfdrehung in Grad."""

    yaw: float
    pitch: float
    roll: float


def rotation_matrix_to_head_pose(matrix: np.ndarray) -> HeadPose:
    """Konvertiert die 3×3-Rotation einer 4×4-Matrix in Yaw/Pitch/Roll."""

    rotation = np.asarray(matrix, dtype=np.float64)[:3, :3]
    axis_length = math.sqrt(rotation[0, 0] ** 2 + rotation[1, 0] ** 2)
    singular = axis_length < 1e-6

    if not singular:
        pitch = math.atan2(rotation[2, 1], rotation[2, 2])
        yaw = math.atan2(-rotation[2, 0], axis_length)
        roll = math.atan2(rotation[1, 0], rotation[0, 0])
    else:
        pitch = math.atan2(-rotation[1, 2], rotation[1, 1])
        yaw = math.atan2(-rotation[2, 0], axis_length)
        roll = 0.0

    return HeadPose(
        yaw=math.degrees(yaw),
        pitch=math.degrees(pitch),
        roll=math.degrees(roll),
    )


class ExponentialSmoother:
    """Glättet Kopfpose, Blendshapes und Landmarken gegen Bildrauschen."""

    def __init__(self, alpha: float = 0.45) -> None:
        if not 0.0 < alpha <= 1.0:
            raise ValueError("alpha muss zwischen 0 und 1 liegen")
        self.alpha = alpha
        self._pose: np.ndarray | None = None
        self._landmarks: np.ndarray | None = None
        self._blendshapes: dict[str, float] = {}

    def pose(self, pose: HeadPose) -> HeadPose:
        current = np.array([pose.yaw, pose.pitch, pose.roll], dtype=np.float64)
        self._pose = self._smooth_array(self._pose, current)
        return HeadPose(*self._pose.tolist())

    def landmarks(self, landmarks: np.ndarray) -> np.ndarray:
        self._landmarks = self._smooth_array(self._landmarks, landmarks)
        return self._landmarks.copy()

    def blendshapes(self, values: dict[str, float]) -> dict[str, float]:
        for name, value in values.items():
            previous = self._blendshapes.get(name, value)
            self._blendshapes[name] = previous + (value - previous) * self.alpha
        return dict(self._blendshapes)

    def reset(self) -> None:
        self._pose = None
        self._landmarks = None
        self._blendshapes.clear()

    def _smooth_array(
        self, previous: np.ndarray | None, current: np.ndarray
    ) -> np.ndarray:
        current = np.asarray(current, dtype=np.float64)
        if previous is None or previous.shape != current.shape:
            return current.copy()
        return previous + (current - previous) * self.alpha


class JsonlRecorder:
    """Schreibt pro Kamerabild einen JSON-Datensatz für spätere Analysen."""

    def __init__(self, output_directory: Path) -> None:
        self.output_directory = output_directory
        self._file = None
        self.path: Path | None = None

    @property
    def active(self) -> bool:
        return self._file is not None

    def toggle(self) -> Path | None:
        if self.active:
            return self.stop()
        return self.start()

    def start(self) -> Path:
        self.output_directory.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.path = self.output_directory / f"gesicht_{timestamp}.jsonl"
        self._file = self.path.open("w", encoding="utf-8")
        return self.path

    def stop(self) -> Path | None:
        if self._file is not None:
            self._file.close()
            self._file = None
        return self.path

    def write(
        self,
        timestamp_ms: int,
        pose: HeadPose,
        blendshapes: dict[str, float],
        landmarks: np.ndarray,
    ) -> None:
        if self._file is None:
            return

        record = {
            "timestamp_ms": timestamp_ms,
            "head_pose_degrees": {
                "yaw": round(pose.yaw, 4),
                "pitch": round(pose.pitch, 4),
                "roll": round(pose.roll, 4),
            },
            "blendshapes": {
                name: round(float(value), 6)
                for name, value in sorted(blendshapes.items())
            },
            "landmarks": [
                {
                    "index": index,
                    "x": round(float(point[0]), 7),
                    "y": round(float(point[1]), 7),
                    "z": round(float(point[2]), 7),
                }
                for index, point in enumerate(landmarks)
            ],
        }
        self._file.write(json.dumps(record, ensure_ascii=False) + "\n")
        self._file.flush()

    def close(self) -> None:
        self.stop()


def categories_to_dict(categories: Iterable[object]) -> dict[str, float]:
    """Überführt MediaPipe-Kategorien in ein einfach auswertbares Dictionary."""

    return {
        str(category.category_name): float(category.score)
        for category in categories
        if category.category_name
    }
