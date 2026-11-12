from __future__ import annotations

import json
from datetime import UTC, datetime

import cv2
import numpy as np

from fazenda_cv.__main__ import main
from fazenda_cv.detection import SimulatorCowDetector, YoloXOnnxDetector
from fazenda_cv.domain import CountLine, Direction
from fazenda_cv.pipeline import CvPipeline


def scene(position: int | None = None) -> np.ndarray:
    image = np.full((80, 120, 3), (45, 65, 45), dtype=np.uint8)
    cv2.line(image, (20, 20), (100, 20), (70, 110, 145), 3)
    if position is not None:
        cv2.rectangle(image, (position - 6, 35), (position + 6, 49), (180, 180, 180), -1)
    return image


def test_simulator_detector_ignores_empty_scene_and_static_fence() -> None:
    detector = SimulatorCowDetector(min_area=30)
    splash = np.zeros((80, 120, 3), dtype=np.uint8)
    cv2.rectangle(splash, (20, 30), (60, 50), (230, 230, 230), -1)
    assert detector.detect(splash) == []
    assert detector.detect(scene()) == []
    found = detector.detect(scene(40))
    assert len(found) == 1
    assert 35 <= found[0].center[0] <= 45


def test_pipeline_counts_both_directions_and_serializes_events() -> None:
    pipeline = CvPipeline(
        SimulatorCowDetector(min_area=30),
        "simulador-1",
        CountLine(),
    )
    pipeline.process(scene())
    events = []
    for index, position in enumerate((34, 42, 50, 58, 66, 74, 66, 58, 50, 42)):
        result = pipeline.process(
            scene(position), datetime(2026, 10, 20, 10, 0, index * 2, tzinfo=UTC)
        )
        events.extend(result.events)
    assert [event.direction for event in events] == [Direction.IN, Direction.OUT]
    assert pipeline.counter.in_count == 1
    assert pipeline.counter.out_count == 1
    payload = events[0].to_dict()
    assert payload["source_id"] == "simulador-1"
    assert payload["schema_version"] == 1
    assert payload["direction"] == "in"
    assert payload["occurred_at"].endswith("+00:00")


def test_video_file_to_cv_events_and_annotated_video(tmp_path, capsys) -> None:
    video = tmp_path / "simulador.avi"
    writer = cv2.VideoWriter(str(video), cv2.VideoWriter_fourcc(*"MJPG"), 10, (120, 80))
    assert writer.isOpened()
    for position in (None, None, 30, 38, 46, 54, 62, 70, 78, 86):
        writer.write(scene(position))
    writer.release()
    events_file = tmp_path / "eventos.jsonl"
    annotated = tmp_path / "demonstracao.avi"

    exit_code = main(
        [
            "--source",
            str(video),
            "--simulator",
            "--events",
            str(events_file),
            "--annotated",
            str(annotated),
        ]
    )

    assert exit_code == 0
    payloads = [json.loads(row) for row in events_file.read_text().splitlines()]
    assert [row["direction"] for row in payloads] == ["in"]
    assert payloads[0]["time_basis"] == "replay"
    assert payloads[0]["video_offset_ms"] == 400
    assert payloads[0]["session_id"]
    assert annotated.is_file()
    output = cv2.VideoCapture(str(annotated))
    assert output.get(cv2.CAP_PROP_FRAME_COUNT) == 10
    output.release()
    assert "1 entradas" in capsys.readouterr().err


def test_yolox_adapter_uses_letterboxed_bgr_and_raw_output() -> None:
    class FakeSession:
        def __init__(self) -> None:
            self.tensor: np.ndarray | None = None

        def run(self, names, feeds):
            self.tensor = next(iter(feeds.values()))
            output = np.zeros((1, 3549, 85), dtype=np.float32)
            output[0, 100, :4] = (0.5, 0.5, 2, 2)
            output[0, 100, 4] = 1
            output[0, 100, 24] = 0.9
            return [output]

    detector = YoloXOnnxDetector.__new__(YoloXOnnxDetector)
    detector.session = FakeSession()
    detector.input_name = "images"
    detector.input_size = 416
    detector.class_id = 19
    detector.confidence_threshold = 0.35
    detector.nms_threshold = 0.45
    frame = np.full((208, 416, 3), (10, 20, 30), dtype=np.uint8)

    detections = detector.detect(frame)

    assert len(detections) == 1
    assert detections[0].class_id == 19
    assert detector.session.tensor is not None
    assert detector.session.tensor.shape == (1, 3, 416, 416)
    assert detector.session.tensor[0, :, 0, 0].tolist() == [10, 20, 30]
    assert detector.session.tensor[0, :, 300, 0].tolist() == [114, 114, 114]
