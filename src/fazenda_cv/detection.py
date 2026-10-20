from __future__ import annotations

from typing import Protocol

import cv2
import numpy as np

from fazenda_cv.domain import Detection


class Detector(Protocol):
    model_version: str

    def detect(self, frame: np.ndarray) -> list[Detection]: ...


class GreenMarkerDetector:
    """Synthetic-fixture detector. Green markers stand in for objects in test videos."""

    model_version = "synthetic-green-marker-1"

    def detect(self, frame: np.ndarray) -> list[Detection]:
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        mask = cv2.inRange(hsv, np.array((35, 80, 80)), np.array((90, 255, 255)))
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        results = []
        for contour in contours:
            area = cv2.contourArea(contour)
            if area < 100:
                continue
            x, y, width, height = cv2.boundingRect(contour)
            results.append(Detection(x, y, x + width, y + height, 0.99, 19))
        return results


class YoloXOnnxDetector:
    """YOLOX raw-output adapter using ONNX Runtime and OpenCV preprocessing."""

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

        self.session = ort.InferenceSession(model_path, providers=["CPUExecutionProvider"])
        self.input_name = self.session.get_inputs()[0].name
        self.input_size = input_size
        self.class_id = class_id
        self.confidence_threshold = confidence_threshold
        self.nms_threshold = nms_threshold

    def detect(self, frame: np.ndarray) -> list[Detection]:
        height, width = frame.shape[:2]
        resized = cv2.resize(frame, (self.input_size, self.input_size))
        rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB).astype(np.float32) / 255.0
        tensor = np.transpose(rgb, (2, 0, 1))[None, ...]
        output = self.session.run(None, {self.input_name: tensor})[0]
        output = np.asarray(output).squeeze(0)
        if output.ndim != 2 or output.shape[1] <= 5 + self.class_id:
            raise ValueError("Modelo ONNX deve gerar [1, anchors, 5 + classes] no formato YOLOX")

        strides = (8, 16, 32)
        grids: list[np.ndarray] = []
        expanded_strides: list[np.ndarray] = []
        for stride in strides:
            grid_size = self.input_size // stride
            yv, xv = np.meshgrid(np.arange(grid_size), np.arange(grid_size), indexing="ij")
            grids.append(np.stack((xv, yv), axis=2).reshape(1, -1, 2))
            expanded_strides.append(np.full((1, grid_size * grid_size, 1), stride))
        grid = np.concatenate(grids, axis=1).squeeze(0)
        stride_values = np.concatenate(expanded_strides, axis=1).squeeze(0)
        if len(output) != len(grid):
            raise ValueError("Quantidade de âncoras do modelo não corresponde ao input YOLOX")
        boxes = output[:, :4].copy()
        boxes[:, :2] = (boxes[:, :2] + grid) * stride_values
        boxes[:, 2:4] = np.exp(boxes[:, 2:4]) * stride_values
        scores = output[:, 4] * output[:, 5 + self.class_id]
        selected = np.flatnonzero(scores >= self.confidence_threshold)
        if not len(selected):
            return []
        xyxy = np.empty((len(selected), 4), dtype=np.float32)
        xyxy[:, 0] = boxes[selected, 0] - boxes[selected, 2] / 2
        xyxy[:, 1] = boxes[selected, 1] - boxes[selected, 3] / 2
        xyxy[:, 2] = boxes[selected, 0] + boxes[selected, 2] / 2
        xyxy[:, 3] = boxes[selected, 1] + boxes[selected, 3] / 2
        indices = cv2.dnn.NMSBoxes(
            xyxy.tolist(), scores[selected].tolist(), self.confidence_threshold, self.nms_threshold
        )
        if len(indices) == 0:
            return []
        scale_x, scale_y = width / self.input_size, height / self.input_size
        return [
            Detection(
                max(0, float(xyxy[i, 0] * scale_x)),
                max(0, float(xyxy[i, 1] * scale_y)),
                min(width, float(xyxy[i, 2] * scale_x)),
                min(height, float(xyxy[i, 3] * scale_y)),
                float(scores[selected[i]]),
                self.class_id,
            )
            for i in np.asarray(indices).reshape(-1)
        ]
