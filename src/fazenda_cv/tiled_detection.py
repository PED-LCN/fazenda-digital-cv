"""Optional tiled inference for high-resolution fixed-camera video."""

from __future__ import annotations

from collections.abc import Iterator

import numpy as np

from fazenda_cv.detection import Detector
from fazenda_cv.domain import Detection


def _starts(length: int, tile_size: int, step: int) -> list[int]:
    if length <= tile_size:
        return [0]
    last = length - tile_size
    starts = list(range(0, last + 1, step))
    if starts[-1] != last:
        starts.append(last)
    return starts


def _tiles(
    width: int, height: int, tile_size: int, overlap: int
) -> Iterator[tuple[int, int, int, int]]:
    step = tile_size - overlap
    for y in _starts(height, tile_size, step):
        for x in _starts(width, tile_size, step):
            yield x, y, min(x + tile_size, width), min(y + tile_size, height)


def _intersection_over_union(left: Detection, right: Detection) -> float:
    x1 = max(left.x1, right.x1)
    y1 = max(left.y1, right.y1)
    x2 = min(left.x2, right.x2)
    y2 = min(left.y2, right.y2)
    intersection = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    left_area = max(0.0, left.x2 - left.x1) * max(0.0, left.y2 - left.y1)
    right_area = max(0.0, right.x2 - right.x1) * max(0.0, right.y2 - right.y1)
    union = left_area + right_area - intersection
    return intersection / union if union > 0 else 0.0


class TiledDetector:
    """Run a detector on overlapping crops, then merge boxes in frame coordinates."""

    def __init__(
        self,
        detector: Detector,
        tile_size: int,
        overlap: int = 0,
        nms_threshold: float = 0.5,
    ) -> None:
        if tile_size <= 0 or overlap < 0 or overlap >= tile_size:
            raise ValueError("tile_size deve ser positivo e overlap menor que tile_size")
        if not 0 < nms_threshold <= 1:
            raise ValueError("nms_threshold deve estar em (0, 1]")
        self.detector = detector
        self.tile_size = tile_size
        self.overlap = overlap
        self.nms_threshold = nms_threshold
        self.model_version = f"{detector.model_version}:tiles-{tile_size}-{overlap}"

    def detect(self, frame: np.ndarray) -> list[Detection]:
        height, width = frame.shape[:2]
        candidates = []
        for x1, y1, x2, y2 in _tiles(width, height, self.tile_size, self.overlap):
            for item in self.detector.detect(frame[y1:y2, x1:x2]):
                candidates.append(
                    Detection(
                        max(0.0, min(width, item.x1 + x1)),
                        max(0.0, min(height, item.y1 + y1)),
                        max(0.0, min(width, item.x2 + x1)),
                        max(0.0, min(height, item.y2 + y1)),
                        item.confidence,
                        item.class_id,
                    )
                )
        kept: list[Detection] = []
        for item in sorted(candidates, key=lambda box: box.confidence, reverse=True):
            if all(
                item.class_id != previous.class_id
                or _intersection_over_union(item, previous) < self.nms_threshold
                for previous in kept
            ):
                kept.append(item)
        return kept
