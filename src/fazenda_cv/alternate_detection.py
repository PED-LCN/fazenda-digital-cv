"""Optional CPU detectors for the cattle benchmark."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from math import isfinite
from pathlib import Path

import cv2
import numpy as np

from fazenda_cv.domain import Detection


def cattle_boxes(
    frame: np.ndarray,
    boxes: Iterable[Sequence[float]],
    scores: Iterable[float],
    labels: Iterable[int],
    class_id: int,
    confidence: float,
) -> list[Detection]:
    height, width = frame.shape[:2]
    detections = []
    for box, score, label in zip(boxes, scores, labels, strict=True):
        if label != class_id or not isfinite(score) or not confidence <= score <= 1:
            continue
        if not all(map(isfinite, box)):
            continue
        x1, y1, x2, y2 = box
        x1, x2 = max(0.0, x1), min(width, x2)
        y1, y2 = max(0.0, y1), min(height, y2)
        if x1 < x2 and y1 < y2:
            detections.append(Detection(x1, y1, x2, y2, score, class_id))
    return detections


class YoloV8CattleDetector:
    def __init__(self, path: Path, digest: str, size: int, confidence: float, threads: int) -> None:
        import torch
        from ultralytics import YOLO

        torch.set_num_threads(threads)
        # NumPy inputs to Ultralytics are BGR; the library handles RGB conversion.
        self.model = YOLO(str(path), task="detect")
        names = self.model.names
        if len(names) != 1 or str(names[0]).lower() not in {"cow", "cattle"}:
            raise ValueError("O checkpoint YOLOv8 deve ter uma única classe bovina")
        self.model_version = f"yolov8:sha256:{digest[:12]}"
        self.size = size
        self.confidence = confidence

    def detect(self, frame: np.ndarray) -> list[Detection]:
        if not frame.size:
            return []
        result = self.model.predict(
            source=frame,
            device="cpu",
            imgsz=self.size,
            conf=self.confidence,
            iou=0.45,
            classes=[0],
            verbose=False,
        )[0].boxes
        return cattle_boxes(
            frame,
            result.xyxy.tolist(),
            result.conf.tolist(),
            result.cls.tolist(),
            0,
            self.confidence,
        )


class RTDetrCattleDetector:
    def __init__(self, path: Path, digest: str, confidence: float, threads: int) -> None:
        import torch
        from transformers import RTDetrForObjectDetection, RTDetrImageProcessor

        torch.set_num_threads(threads)
        self.torch = torch
        self.processor = RTDetrImageProcessor.from_pretrained(path, local_files_only=True)
        self.model = RTDetrForObjectDetection.from_pretrained(
            path, local_files_only=True, use_safetensors=True
        ).eval()
        (self.class_id,) = (
            i for i, name in self.model.config.id2label.items() if name.lower() == "cow"
        )
        self.confidence = confidence
        self.model_version = f"rtdetr:sha256:{digest[:12]}"

    def detect(self, frame: np.ndarray) -> list[Detection]:
        if not frame.size:
            return []
        height, width = frame.shape[:2]
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        inputs = self.processor(images=rgb, return_tensors="pt")
        with self.torch.inference_mode():
            outputs = self.model(**inputs)
            result = self.processor.post_process_object_detection(
                outputs, target_sizes=[(height, width)], threshold=self.confidence
            )[0]
        return cattle_boxes(
            frame,
            result["boxes"].tolist(),
            result["scores"].tolist(),
            result["labels"].tolist(),
            self.class_id,
            self.confidence,
        )
