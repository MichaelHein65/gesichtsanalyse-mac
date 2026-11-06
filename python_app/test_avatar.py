import unittest

import numpy as np

from avatar import render_avatar
from face_analysis import HeadPose


class AvatarTests(unittest.TestCase):
    def test_avatar_has_requested_image_shape(self) -> None:
        image = render_avatar(640, 480, HeadPose(0.0, 0.0, 0.0), {})
        self.assertEqual(image.shape, (480, 640, 3))
        self.assertEqual(image.dtype, np.uint8)

    def test_blink_changes_avatar_pixels(self) -> None:
        neutral = render_avatar(640, 480, HeadPose(0.0, 0.0, 0.0), {})
        blink = render_avatar(
            640,
            480,
            HeadPose(0.0, 0.0, 0.0),
            {"eyeBlinkLeft": 1.0, "eyeBlinkRight": 1.0},
        )
        self.assertFalse(np.array_equal(neutral, blink))

    def test_head_roll_changes_avatar_pixels(self) -> None:
        neutral = render_avatar(640, 480, HeadPose(0.0, 0.0, 0.0), {})
        tilted = render_avatar(640, 480, HeadPose(0.0, 0.0, 20.0), {})
        self.assertFalse(np.array_equal(neutral, tilted))


if __name__ == "__main__":
    unittest.main()
