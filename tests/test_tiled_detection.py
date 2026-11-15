from __future__ import annotations

import numpy as np
import pytest

from fazenda_cv.__main__ import main
from fazenda_cv.domain import Detection
from fazenda_cv.tiled_detection import TiledDetector


def coordinate_frame(width: int, height: int) -> np.ndarray:
    frame = np.zeros((height, width, 3), dtype=np.uint8)
    frame[:, :, 0] = np.arange(width)
    frame[:, :, 1] = np.arange(height)[:, None]
    return frame


class LocalBoxDetector:
    model_version = "fake"

    def __init__(self) -> None:
        self.crops: list[tuple[int, int, int, int]] = []

    def detect(self, frame: np.ndarray) -> list[Detection]:
        y, x = int(frame[0, 0, 1]), int(frame[0, 0, 0])
        self.crops.append((x, y, frame.shape[1], frame.shape[0]))
        return [Detection(1, 1, 2, 2, 0.9, 19)]


def test_tile_boundaries_and_global_coordinates():
    base = LocalBoxDetector()
    detector = TiledDetector(base, tile_size=4, overlap=1)

    boxes = detector.detect(coordinate_frame(7, 5))

    assert base.crops == [(0, 0, 4, 4), (3, 0, 4, 4), (0, 1, 4, 4), (3, 1, 4, 4)]
    assert [(box.x1, box.y1, box.x2, box.y2) for box in boxes] == [
        (1, 1, 2, 2),
        (4, 1, 5, 2),
        (1, 2, 2, 3),
        (4, 2, 5, 3),
    ]
    assert detector.model_version == "fake:tiles-4-1"


def test_tile_larger_than_frame_runs_once():
    base = LocalBoxDetector()
    boxes = TiledDetector(base, tile_size=10).detect(coordinate_frame(5, 4))
    assert base.crops == [(0, 0, 5, 4)]
    assert len(boxes) == 1


def test_global_nms_deduplicates_the_same_cow_across_crops():
    class SharedCowDetector:
        model_version = "fake"

        def detect(self, frame: np.ndarray) -> list[Detection]:
            y, x = int(frame[0, 0, 1]), int(frame[0, 0, 0])
            return [Detection(2.5 - x, 2.5 - y, 3.5 - x, 3.5 - y, 0.8, 19)]

    boxes = TiledDetector(SharedCowDetector(), tile_size=4, overlap=2).detect(
        coordinate_frame(6, 6)
    )
    assert len(boxes) == 1
    assert (boxes[0].x1, boxes[0].y1, boxes[0].x2, boxes[0].y2) == (2.5, 2.5, 3.5, 3.5)


@pytest.mark.parametrize("size,overlap", [(0, 0), (4, -1), (4, 4), (4, 5)])
def test_invalid_tiling_parameters(size: int, overlap: int):
    with pytest.raises(ValueError):
        TiledDetector(LocalBoxDetector(), tile_size=size, overlap=overlap)


def test_cli_requires_original_resolution_for_tiled_model(capsys):
    with pytest.raises(SystemExit) as error:
        main(["--source", "sample.mp4", "--model", "weights.onnx", "--tile-size", "736"])
    assert error.value.code == 2
    assert "--max-width 0" in capsys.readouterr().err
