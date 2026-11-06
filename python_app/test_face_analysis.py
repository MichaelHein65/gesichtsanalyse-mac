import tempfile
import unittest
from pathlib import Path

import numpy as np

from face_analysis import ExponentialSmoother, HeadPose, JsonlRecorder, rotation_matrix_to_head_pose


class FaceAnalysisTests(unittest.TestCase):
    def test_identity_matrix_is_neutral_pose(self) -> None:
        pose = rotation_matrix_to_head_pose(np.eye(4))
        self.assertAlmostEqual(pose.yaw, 0.0)
        self.assertAlmostEqual(pose.pitch, 0.0)
        self.assertAlmostEqual(pose.roll, 0.0)

    def test_smoother_interpolates_pose(self) -> None:
        smoother = ExponentialSmoother(alpha=0.5)
        smoother.pose(HeadPose(0.0, 0.0, 0.0))
        pose = smoother.pose(HeadPose(20.0, 10.0, -10.0))
        self.assertEqual(pose, HeadPose(10.0, 5.0, -5.0))

    def test_recorder_writes_all_measurement_groups(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            recorder = JsonlRecorder(Path(directory))
            path = recorder.start()
            recorder.write(
                42,
                HeadPose(1.0, 2.0, 3.0),
                {"jawOpen": 0.75},
                np.array([[0.1, 0.2, -0.3]]),
            )
            recorder.close()
            content = path.read_text(encoding="utf-8")
            self.assertIn('"head_pose_degrees"', content)
            self.assertIn('"jawOpen": 0.75', content)
            self.assertIn('"landmarks"', content)


if __name__ == "__main__":
    unittest.main()
