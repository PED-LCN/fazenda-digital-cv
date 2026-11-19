from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import Mock

import numpy as np

from fazenda_cv.alternate_detection import RTDetrCattleDetector, YoloV8CattleDetector


def test_rtdetr_converts_color_and_keeps_clipped_cow_boxes():
    detector = RTDetrCattleDetector.__new__(RTDetrCattleDetector)
    detector.torch = SimpleNamespace(inference_mode=nullcontext)
    detector.confidence, detector.class_id = 0.2, 4
    detector.model = Mock()
    detector.processor = Mock(return_value={})
    detector.processor.post_process_object_detection.return_value = [
        {
            "boxes": np.array([[-2, 0, 7, 2], [0, 0, 1, 1], [6, 0, 9, 1], [1, 0, 2, 1]]),
            "scores": np.array([0.9, 0.9, 0.8, 0.1]),
            "labels": np.array([4, 8, 4, 4]),
        }
    ]
    frame = np.full((2, 5, 3), [1, 2, 3], dtype=np.uint8)

    (box,) = detector.detect(frame)

    assert (box.x1, box.y1, box.x2, box.y2, box.class_id) == (0, 0, 5, 2, 4)
    assert detector.processor.call_args.kwargs["images"][0, 0].tolist() == [3, 2, 1]
    assert detector.processor.post_process_object_detection.call_args.kwargs["target_sizes"] == [
        (2, 5)
    ]
    assert detector.detect(np.zeros((0, 0, 3), dtype=np.uint8)) == []


def test_yolov8_keeps_bgr_and_handles_no_detections():
    detector = YoloV8CattleDetector.__new__(YoloV8CattleDetector)
    detector.size, detector.confidence = 640, 0.2
    detector.model = Mock()
    detector.model.predict.return_value = [
        SimpleNamespace(
            boxes=SimpleNamespace(xyxy=np.empty((0, 4)), conf=np.array([]), cls=np.array([]))
        )
    ]
    frame = np.full((2, 5, 3), [1, 2, 3], dtype=np.uint8)
    assert detector.detect(frame) == []
    assert detector.model.predict.call_args.kwargs["source"] is frame
    assert detector.model.predict.call_args.kwargs["classes"] == [0]
