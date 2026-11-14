from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

import cv2
import numpy as np

from fazenda_cv.counter import PassageCounter
from fazenda_cv.detection import Detector
from fazenda_cv.domain import CountLine, Detection, PassageEvent, Track
from fazenda_cv.tracking import CentroidTracker


@dataclass(slots=True)
class FrameResult:
    detections: list[Detection]
    tracks: list[Track]
    events: list[PassageEvent]
    in_count: int
    out_count: int


class CvPipeline:
    """The reusable CV component: frame -> detections -> tracks -> passages."""

    def __init__(
        self,
        detector: Detector,
        source_id: str,
        line: CountLine | None = None,
        tracker: CentroidTracker | None = None,
    ) -> None:
        self.detector = detector
        self.source_id = source_id
        self.line = line or CountLine()
        self.tracker = tracker or CentroidTracker()
        self.counter = PassageCounter(self.line)

    def process(
        self,
        frame: np.ndarray,
        moment: datetime | None = None,
        *,
        session_id: str | None = None,
        video_offset_ms: int | None = None,
        time_basis: str = "live",
    ) -> FrameResult:
        detections = self.detector.detect(frame)
        tracks = self.tracker.update(detections)
        events = self.counter.update(
            tracks,
            (frame.shape[1], frame.shape[0]),
            self.source_id,
            self.detector.model_version,
            moment,
            session_id,
            video_offset_ms,
            time_basis,
        )
        self.counter.retain_tracks(self.tracker.active_ids)
        return FrameResult(
            detections, tracks, events, self.counter.in_count, self.counter.out_count
        )

    def annotate(self, frame: np.ndarray, result: FrameResult) -> np.ndarray:
        image = frame.copy()
        height, width = image.shape[:2]
        start = (int(self.line.start[0] * width), int(self.line.start[1] * height))
        end = (int(self.line.end[0] * width), int(self.line.end[1] * height))
        cv2.line(image, start, end, (0, 220, 255), 2)
        for detection in result.detections:
            cv2.rectangle(
                image,
                (int(detection.x1), int(detection.y1)),
                (int(detection.x2), int(detection.y2)),
                (0, 240, 0),
                2,
            )
        for track in result.tracks:
            x, y = int(track.center[0]), int(track.center[1])
            cv2.circle(image, (x, y), 4, (255, 80, 0), -1)
            cv2.putText(
                image,
                f"#{track.track_id}",
                (x + 6, y),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (255, 255, 255),
                1,
            )
        cv2.rectangle(image, (0, 0), (min(width, 360), 38), (20, 20, 20), -1)
        cv2.putText(
            image,
            f"Entradas: {result.in_count}  Saidas: {result.out_count}",
            (8, 26),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.65,
            (255, 255, 255),
            2,
        )
        return image
