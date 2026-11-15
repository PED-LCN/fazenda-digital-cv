"""Run the actual detector and tracker on frames matched to MOT cattle IDs."""

from __future__ import annotations

from pathlib import Path

import cv2

from fazenda_cv.detection import Detector
from fazenda_cv.mot_data import MotPosition
from fazenda_cv.tracking import CentroidTracker
from fazenda_cv.tracking_evaluation import LabelledPosition, TrackingScore, score_tracks


def score_mot_tracking_video(
    video_path: str | Path,
    detector: Detector,
    tracker: CentroidTracker,
    labels: dict[int, list[MotPosition]],
    *,
    first_frame: int,
    last_frame: int,
    max_match_distance: float,
) -> TrackingScore:
    """Score detector and tracker together on one-indexed video frames."""
    if first_frame < 1 or last_frame < first_frame:
        raise ValueError("Intervalo de quadros inválido")
    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        raise OSError(f"Não foi possível abrir o vídeo: {video_path}")

    def frames():
        try:
            if first_frame > 1 and not capture.set(cv2.CAP_PROP_POS_FRAMES, first_frame - 1):
                raise OSError("Não foi possível posicionar o vídeo no quadro inicial")
            for frame_number in range(first_frame, last_frame + 1):
                ok, image = capture.read()
                if not ok:
                    raise OSError(f"Vídeo incompleto no quadro {frame_number}")
                expected = [
                    LabelledPosition(str(item.object_id), item.center)
                    for item in labels.get(frame_number, [])
                ]
                yield expected, tracker.update(detector.detect(image))
        finally:
            capture.release()

    return score_tracks(frames(), max_distance=max_match_distance)
