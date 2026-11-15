import cv2
import numpy as np
import pytest

from fazenda_cv.domain import Detection
from fazenda_cv.mot_data import MotPosition
from fazenda_cv.mot_tracking import score_mot_tracking_video
from fazenda_cv.tracking import CentroidTracker


def test_scores_real_pipeline_path_with_missing_detection(tmp_path):
    video = tmp_path / "cows.avi"
    writer = cv2.VideoWriter(str(video), cv2.VideoWriter_fourcc(*"MJPG"), 10, (64, 48))
    assert writer.isOpened()
    for _ in range(2):
        writer.write(np.zeros((48, 64, 3), dtype=np.uint8))
    writer.release()

    class Detector:
        model_version = "fake"

        def __init__(self):
            self.calls = 0

        def detect(self, frame):
            self.calls += 1
            return [Detection(10, 10, 20, 20, 0.9, 19)] if self.calls == 1 else []

    labels = {
        1: [MotPosition(1, 3, (15, 15), 1)],
        2: [MotPosition(2, 3, (15, 15), 1)],
    }
    score = score_mot_tracking_video(
        video,
        Detector(),
        CentroidTracker(),
        labels,
        first_frame=1,
        last_frame=2,
        max_match_distance=5,
    )
    assert score.labelled_positions == 2
    assert score.missed_positions == 1


def test_rejects_missing_video(tmp_path):
    with pytest.raises(OSError, match="abrir"):
        score_mot_tracking_video(
            tmp_path / "missing.mp4",
            None,
            CentroidTracker(),
            {},
            first_frame=1,
            last_frame=1,
            max_match_distance=5,
        )
