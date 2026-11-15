import cv2
import numpy as np
import pytest

from fazenda_cv.domain import Detection
from fazenda_cv.mot_boxes import MotBox
from fazenda_cv.mot_evaluation import score_mot_video


def test_scores_decoded_frames_against_scaled_mot_boxes(tmp_path):
    video = tmp_path / "cows.avi"
    writer = cv2.VideoWriter(str(video), cv2.VideoWriter_fourcc(*"MJPG"), 10, (64, 48))
    assert writer.isOpened()
    for _ in range(2):
        writer.write(np.zeros((48, 64, 3), dtype=np.uint8))
    writer.release()

    class Detector:
        model_version = "fake"

        def detect(self, frame):
            return [Detection(10, 10, 20, 20, 0.9, 19)]

    labels = {1: [MotBox(1, 3, (10, 10, 20, 20))]}
    result = score_mot_video(video, Detector(), labels, first_frame=1, last_frame=2)
    assert (result.true_positive, result.false_positive, result.false_negative) == (1, 1, 0)


def test_rejects_incomplete_video(tmp_path):
    with pytest.raises(OSError, match="abrir"):
        score_mot_video(tmp_path / "missing.mp4", None, {}, first_frame=1, last_frame=1)
