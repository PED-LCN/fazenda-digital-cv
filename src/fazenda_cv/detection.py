from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Protocol

import cv2
import numpy as np

from fazenda_cv.domain import Detection


class Detector(Protocol):
    model_version: str

    def detect(self, frame: np.ndarray) -> list[Detection]: ...


class SimulatorCowDetector:
    """Finds the gray cow mesh against the dark green Godot scene.

    These thresholds are specific to the supplied simulation. They are not a
    cattle detector for farm footage, and their score is not calibrated.
    """

    model_version = "simulator-gray-cow-1"

    def __init__(
        self,
        roi: tuple[float, float, float, float] = (0.05, 0.12, 0.98, 0.95),
        min_area: int = 45,
    ) -> None:
        left, top, right, bottom = roi
        if not (0 <= left < right <= 1 and 0 <= top < bottom <= 1):
            raise ValueError("ROI inválida")
        self.roi = roi
        self.min_area = min_area

    def detect(self, frame: np.ndarray) -> list[Detection]:
        height, width = frame.shape[:2]
        x1, y1 = int(self.roi[0] * width), int(self.roi[1] * height)
        x2, y2 = int(self.roi[2] * width), int(self.roi[3] * height)
        hsv = cv2.cvtColor(frame[y1:y2, x1:x2], cv2.COLOR_BGR2HSV)
        pasture = cv2.inRange(hsv[::4, ::4], (35, 40, 25), (95, 255, 255))
        if np.count_nonzero(pasture) / pasture.size < 0.2:
            return []
        mask = cv2.inRange(hsv, (0, 0, 95), (179, 60, 255))
        kernel = np.ones((3, 3), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        result = []
        for contour in contours:
            if cv2.contourArea(contour) < self.min_area:
                continue
            x, y, w, h = cv2.boundingRect(contour)
            result.append(Detection(x + x1, y + y1, x + x1 + w, y + y1 + h, 1.0, 19))
        return result


class YoloXOnnxDetector:
    """YOLOX raw-output ONNX adapter for the real-camera path."""

    model_version = "yolox-onnx"

    def __init__(
        self,
        model_path: str,
        input_size: int = 416,
        class_id: int = 19,
        confidence_threshold: float = 0.35,
        nms_threshold: float = 0.45,
    ) -> None:
        import onnxruntime as ort

        with Path(model_path).open("rb") as weights:
            digest = hashlib.file_digest(weights, "sha256").hexdigest()
        self.model_version = f"yolox-onnx:sha256:{digest[:12]}"
        self.session = ort.InferenceSession(model_path, providers=["CPUExecutionProvider"])
        self.input_name = self.session.get_inputs()[0].name
        self.input_size = input_size
        self.class_id = class_id
        self.confidence_threshold = confidence_threshold
        self.nms_threshold = nms_threshold

    def detect(self, frame: np.ndarray) -> list[Detection]:
        height, width = frame.shape[:2]
        ratio = min(self.input_size / height, self.input_size / width)
        resized = cv2.resize(frame, (int(width * ratio), int(height * ratio)))
        padded = np.full((self.input_size, self.input_size, 3), 114, dtype=np.uint8)
        padded[: resized.shape[0], : resized.shape[1]] = resized
        tensor = np.ascontiguousarray(padded.transpose(2, 0, 1), dtype=np.float32)[None]
        output = np.asarray(self.session.run(None, {self.input_name: tensor})[0]).squeeze(0)
        if output.ndim != 2 or output.shape[1] <= 5 + self.class_id:
            raise ValueError("Saída ONNX esperada: [1, anchors, 5 + classes] de YOLOX")

        grids = []
        expanded_strides = []
        for stride in (8, 16, 32):
            size = self.input_size // stride
            yv, xv = np.meshgrid(np.arange(size), np.arange(size), indexing="ij")
            grids.append(np.stack((xv, yv), axis=2).reshape(-1, 2))
            expanded_strides.append(np.full((size * size, 1), stride))
        grid = np.concatenate(grids)
        stride_values = np.concatenate(expanded_strides)
        if len(output) != len(grid):
            raise ValueError("Quantidade de anchors incompatível com YOLOX e input_size")
        boxes = output[:, :4].copy()
        boxes[:, :2] = (boxes[:, :2] + grid) * stride_values
        boxes[:, 2:4] = np.exp(boxes[:, 2:4]) * stride_values
        scores = output[:, 4] * output[:, 5 + self.class_id]
        selected = np.flatnonzero(scores >= self.confidence_threshold)
        if not len(selected):
            return []
        xywh = np.empty((len(selected), 4), dtype=np.float32)
        xywh[:, 0] = boxes[selected, 0] - boxes[selected, 2] / 2
        xywh[:, 1] = boxes[selected, 1] - boxes[selected, 3] / 2
        xywh[:, 2:4] = boxes[selected, 2:4]
        keep = cv2.dnn.NMSBoxes(
            xywh.tolist(), scores[selected].tolist(), self.confidence_threshold, self.nms_threshold
        )
        return [
            Detection(
                max(0, float(xywh[i, 0] / ratio)),
                max(0, float(xywh[i, 1] / ratio)),
                min(width, float((xywh[i, 0] + xywh[i, 2]) / ratio)),
                min(height, float((xywh[i, 1] + xywh[i, 3]) / ratio)),
                float(scores[selected[i]]),
                self.class_id,
            )
            for i in np.asarray(keep).reshape(-1)
        ]
