"""Prozeduraler 2D-Avatar, gesteuert durch MediaPipe-Blendshapes."""

from __future__ import annotations

import cv2
import numpy as np

from face_analysis import HeadPose


def _value(blendshapes: dict[str, float], name: str) -> float:
    return float(np.clip(blendshapes.get(name, 0.0), 0.0, 1.0))


def _background(width: int, height: int) -> np.ndarray:
    top = np.array([38, 30, 54], dtype=np.float32)
    bottom = np.array([18, 48, 62], dtype=np.float32)
    blend = np.linspace(0.0, 1.0, height, dtype=np.float32)[:, None, None]
    row = top[None, None, :] * (1.0 - blend) + bottom[None, None, :] * blend
    image = np.repeat(row, width, axis=1).astype(np.uint8)

    # Dezente Lichtkreise geben dem Avatar räumliche Tiefe.
    cv2.circle(image, (width // 2, height // 2), min(width, height) // 2, (42, 62, 78), -1)
    cv2.circle(image, (width // 2, height // 2), min(width, height) // 3, (52, 72, 88), -1)
    return image


def _composite_rgba(background: np.ndarray, foreground: np.ndarray) -> np.ndarray:
    alpha = foreground[:, :, 3:4].astype(np.float32) / 255.0
    color = foreground[:, :, :3].astype(np.float32)
    result = color * alpha + background.astype(np.float32) * (1.0 - alpha)
    return result.astype(np.uint8)


def _eye_gaze(blendshapes: dict[str, float], side: str) -> tuple[float, float]:
    horizontal = _value(blendshapes, f"eyeLookOut{side}") - _value(
        blendshapes, f"eyeLookIn{side}"
    )
    vertical = _value(blendshapes, f"eyeLookDown{side}") - _value(
        blendshapes, f"eyeLookUp{side}"
    )
    return horizontal, vertical


def render_avatar(
    width: int,
    height: int,
    pose: HeadPose | None,
    blendshapes: dict[str, float],
) -> np.ndarray:
    """Rendert einen freundlichen Avatar als BGR-Bild für OpenCV."""

    background = _background(width, height)
    pose = pose or HeadPose(0.0, 0.0, 0.0)
    scale = min(width, height) / 720.0
    center_x = int(width * 0.5 + np.clip(pose.yaw, -35.0, 35.0) * 1.8 * scale)
    center_y = int(height * 0.47 + np.clip(pose.pitch, -25.0, 25.0) * 1.3 * scale)
    head_width = int(330 * scale)
    head_height = int(430 * scale)
    yaw_factor = float(np.clip(pose.yaw / 45.0, -0.65, 0.65))

    layer = np.zeros((height, width, 4), dtype=np.uint8)
    opaque = 255

    # Der Körper bleibt ruhig, während sich der Kopf unabhängig neigt.
    cv2.ellipse(
        background,
        (center_x, int(height * 0.92)),
        (int(250 * scale), int(145 * scale)),
        0,
        180,
        360,
        (72, 94, 185),
        -1,
        cv2.LINE_AA,
    )
    cv2.rectangle(
        background,
        (center_x - int(65 * scale), center_y + int(150 * scale)),
        (center_x + int(65 * scale), center_y + int(265 * scale)),
        (145, 180, 218),
        -1,
    )

    # Ohren gehören zur rotierenden Kopfebene.
    for side in (-1, 1):
        cv2.ellipse(
            layer,
            (center_x + side * head_width // 2, center_y + int(8 * scale)),
            (int(34 * scale), int(62 * scale)),
            0,
            0,
            360,
            (135, 174, 215, opaque),
            -1,
            cv2.LINE_AA,
        )

    # Kopf, Schatten und Haare.
    cv2.ellipse(
        layer,
        (center_x + int(9 * scale), center_y + int(10 * scale)),
        (head_width // 2, head_height // 2),
        0,
        0,
        360,
        (70, 78, 105, 150),
        -1,
        cv2.LINE_AA,
    )
    cv2.ellipse(
        layer,
        (center_x, center_y),
        (head_width // 2, head_height // 2),
        0,
        0,
        360,
        (164, 195, 229, opaque),
        -1,
        cv2.LINE_AA,
    )
    cv2.ellipse(
        layer,
        (center_x, center_y - int(158 * scale)),
        (int(167 * scale), int(92 * scale)),
        0,
        180,
        360,
        (62, 54, 76, opaque),
        -1,
        cv2.LINE_AA,
    )

    feature_shift = int(yaw_factor * 38 * scale)
    eye_y = center_y - int(52 * scale)
    eye_distance = int((92 - abs(yaw_factor) * 18) * scale)
    eye_width = int(55 * scale)

    # Wangen reagieren auf Lächeln und Zusammenkneifen der Augen.
    smile = (_value(blendshapes, "mouthSmileLeft") + _value(blendshapes, "mouthSmileRight")) / 2
    for side, name in ((-1, "cheekSquintLeft"), (1, "cheekSquintRight")):
        intensity = max(smile * 0.65, _value(blendshapes, name))
        cheek_color = (125, 145, 245, int(40 + intensity * 100))
        cv2.ellipse(
            layer,
            (center_x + feature_shift + side * int(108 * scale), center_y + int(54 * scale)),
            (int(36 * scale), int(19 * scale)),
            0,
            0,
            360,
            cheek_color,
            -1,
            cv2.LINE_AA,
        )

    # Augen, Lider, Pupillen und Blickrichtung.
    for side, suffix in ((-1, "Left"), (1, "Right")):
        eye_x = center_x + feature_shift + side * eye_distance
        blink = _value(blendshapes, f"eyeBlink{suffix}")
        wide = _value(blendshapes, f"eyeWide{suffix}")
        eye_height = max(int(3 * scale), int((30 + wide * 18) * (1.0 - blink) * scale))

        cv2.ellipse(
            layer,
            (eye_x, eye_y),
            (eye_width, eye_height),
            0,
            0,
            360,
            (247, 247, 244, opaque),
            -1,
            cv2.LINE_AA,
        )
        if eye_height > int(8 * scale):
            gaze_x, gaze_y = _eye_gaze(blendshapes, suffix)
            pupil_center = (
                eye_x + int(gaze_x * 17 * scale),
                eye_y + int(gaze_y * 10 * scale),
            )
            cv2.circle(layer, pupil_center, int(14 * scale), (65, 105, 120, opaque), -1, cv2.LINE_AA)
            cv2.circle(layer, pupil_center, int(7 * scale), (32, 30, 39, opaque), -1, cv2.LINE_AA)
            cv2.circle(
                layer,
                (pupil_center[0] - int(3 * scale), pupil_center[1] - int(4 * scale)),
                max(1, int(3 * scale)),
                (255, 255, 255, opaque),
                -1,
                cv2.LINE_AA,
            )
        else:
            cv2.line(
                layer,
                (eye_x - eye_width, eye_y),
                (eye_x + eye_width, eye_y),
                (70, 58, 73, opaque),
                max(2, int(4 * scale)),
                cv2.LINE_AA,
            )

        brow_up = max(
            _value(blendshapes, f"browOuterUp{suffix}"),
            _value(blendshapes, "browInnerUp"),
        )
        brow_down = _value(blendshapes, f"browDown{suffix}")
        brow_y = eye_y - int((55 + brow_up * 24 - brow_down * 18) * scale)
        inner_y = brow_y - int(_value(blendshapes, "browInnerUp") * 15 * scale)
        points = np.array(
            [
                [eye_x - side * int(42 * scale), inner_y],
                [eye_x, brow_y - int(8 * scale)],
                [eye_x + side * int(47 * scale), brow_y],
            ],
            dtype=np.int32,
        )
        cv2.polylines(
            layer,
            [points],
            False,
            (67, 51, 69, opaque),
            max(2, int(8 * scale)),
            cv2.LINE_AA,
        )

    # Nase folgt der Drehung und verstärkt dadurch die Kopfrichtung.
    nose_x = center_x + feature_shift + int(yaw_factor * 28 * scale)
    nose_y = center_y + int(20 * scale)
    nose_points = np.array(
        [
            [nose_x, nose_y - int(30 * scale)],
            [nose_x - int(12 * scale), nose_y + int(32 * scale)],
            [nose_x + int(17 * scale), nose_y + int(34 * scale)],
        ],
        dtype=np.int32,
    )
    cv2.polylines(layer, [nose_points], False, (120, 147, 185, opaque), max(2, int(4 * scale)), cv2.LINE_AA)

    # Mundform aus Kieferöffnung, Lächeln, Stirnrunzeln und Trichtermund.
    jaw_open = _value(blendshapes, "jawOpen")
    frown = (_value(blendshapes, "mouthFrownLeft") + _value(blendshapes, "mouthFrownRight")) / 2
    pucker = max(_value(blendshapes, "mouthPucker"), _value(blendshapes, "mouthFunnel"))
    mouth_shift = (_value(blendshapes, "mouthRight") - _value(blendshapes, "mouthLeft")) * 28
    mouth_x = center_x + feature_shift + int(mouth_shift * scale)
    mouth_y = center_y + int(105 * scale)
    mouth_width = int((100 + smile * 45 - pucker * 55) * scale)
    mouth_height = max(int(5 * scale), int((8 + jaw_open * 65 + pucker * 18) * scale))

    if mouth_height > int(10 * scale):
        cv2.ellipse(
            layer,
            (mouth_x, mouth_y),
            (mouth_width, mouth_height),
            0,
            0,
            360,
            (62, 38, 65, opaque),
            -1,
            cv2.LINE_AA,
        )
        if smile > 0.25:
            cv2.ellipse(
                layer,
                (mouth_x, mouth_y - mouth_height // 3),
                (int(mouth_width * 0.72), max(2, int(8 * scale))),
                0,
                0,
                180,
                (245, 245, 238, opaque),
                -1,
                cv2.LINE_AA,
            )

    lip_color = (95, 65, 155, opaque)
    lip_thickness = max(2, int(7 * scale))
    if mouth_height > int(10 * scale):
        cv2.ellipse(
            layer,
            (mouth_x, mouth_y),
            (mouth_width, mouth_height),
            0,
            0,
            360,
            lip_color,
            lip_thickness,
            cv2.LINE_AA,
        )
    elif smile > frown + 0.05:
        cv2.ellipse(
            layer,
            (mouth_x, mouth_y - int(smile * 20 * scale)),
            (mouth_width, max(int(12 * scale), int(smile * 42 * scale))),
            0,
            0,
            180,
            lip_color,
            lip_thickness,
            cv2.LINE_AA,
        )
    elif frown > smile + 0.05:
        cv2.ellipse(
            layer,
            (mouth_x, mouth_y + int(frown * 18 * scale)),
            (mouth_width, max(int(12 * scale), int(frown * 38 * scale))),
            0,
            180,
            360,
            lip_color,
            lip_thickness,
            cv2.LINE_AA,
        )
    else:
        cv2.line(
            layer,
            (mouth_x - mouth_width, mouth_y),
            (mouth_x + mouth_width, mouth_y),
            lip_color,
            lip_thickness,
            cv2.LINE_AA,
        )

    # Roll rotiert den vollständigen Avatar-Kopf wie die reale Kopfhaltung.
    rotation = cv2.getRotationMatrix2D((center_x, center_y), -pose.roll, 1.0)
    rotated = cv2.warpAffine(
        layer,
        rotation,
        (width, height),
        flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT,
        borderValue=(0, 0, 0, 0),
    )
    return _composite_rgba(background, rotated)
