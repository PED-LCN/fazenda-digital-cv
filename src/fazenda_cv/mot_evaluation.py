"""Frame-aligned detector evaluation against real MOT cattle boxes."""

from __future__ import annotations

from pathlib import Path

import cv2

from fazenda_cv.detection import Detector
from fazenda_cv.model_qualification import DetectionScore, score_frame
from fazenda_cv.mot_boxes import MotBox


def score_mot_video(
    video_path: str | Path,
    detector: Detector,
    labels: dict[int, list[MotBox]],
    *,
    first_frame: int,
    last_frame: int,
    iou_threshold: float = 0.5,
) -> DetectionScore:
    """Score each decoded frame; MOT frame 1 is the first decoded video frame."""
    if first_frame < 1 or last_frame < first_frame:
        raise ValueError("Intervalo de quadros inválido")
    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise OSError(f"Não foi possível abrir o vídeo: {video_path}")
    try:
        if first_frame > 1 and not capture.set(cv2.CAP_PROP_POS_FRAMES, first_frame - 1):
            raise OSError("Não foi possível posicionar o vídeo no quadro inicial")
        true_positive = false_positive = false_negative = 0
        for frame_number in range(first_frame, last_frame + 1):
            ok, image = capture.read()
            if not ok:
                raise OSError(f"Vídeo incompleto no quadro {frame_number}")
            expected = [item.xyxy for item in labels.get(frame_number, [])]
            score = score_frame(detector.detect(image), expected, iou_threshold=iou_threshold)
            true_positive += score.true_positive
            false_positive += score.false_positive
            false_negative += score.false_negative
        return DetectionScore(true_positive, false_positive, false_negative)
    finally:
        capture.release()
