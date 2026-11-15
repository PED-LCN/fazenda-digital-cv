"""Provenance and box-level measurements for a real cattle detector."""

from __future__ import annotations

import hashlib
import tomllib
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from fazenda_cv.domain import Detection


@dataclass(frozen=True, slots=True)
class ModelCard:
    path: Path
    source_url: str
    license: str
    sha256: str
    input_size: int
    cattle_class_id: int
    class_names: tuple[str, ...]


def load_model_card(path: str | Path) -> ModelCard:
    """Verify that the declared YOLOX asset exists and matches its model card."""
    card_path = Path(path)
    with card_path.open("rb") as file:
        data = tomllib.load(file)
    fields = {
        "path",
        "source_url",
        "license",
        "sha256",
        "input_size",
        "cattle_class_id",
        "class_names",
    }
    if set(data) != fields:
        raise ValueError("Model card exige path, origem, licença, hash, entrada e classes")
    model_path = (card_path.parent / data["path"]).resolve()
    url = urlparse(data["source_url"])
    if url.scheme not in {"http", "https"} or not url.netloc or not data["license"].strip():
        raise ValueError("Origem ou licença do modelo inválida")
    size = data["input_size"]
    class_id = data["cattle_class_id"]
    names = data["class_names"]
    if (
        isinstance(size, bool)
        or not isinstance(size, int)
        or size < 32
        or size % 32
        or isinstance(class_id, bool)
        or not isinstance(class_id, int)
        or not isinstance(names, list)
        or not names
        or any(not isinstance(name, str) or not name.strip() for name in names)
        or not 0 <= class_id < len(names)
    ):
        raise ValueError("Formato de entrada ou mapa de classes inválido")
    with model_path.open("rb") as file:
        digest = hashlib.file_digest(file, "sha256").hexdigest()
    if digest != data["sha256"].lower():
        raise ValueError("SHA-256 dos pesos não corresponde ao model card")
    return ModelCard(
        model_path, data["source_url"], data["license"], digest, size, class_id, tuple(names)
    )


@dataclass(frozen=True, slots=True)
class DetectionScore:
    true_positive: int
    false_positive: int
    false_negative: int

    @property
    def precision(self) -> float:
        total = self.true_positive + self.false_positive
        return self.true_positive / total if total else 0.0

    @property
    def recall(self) -> float:
        total = self.true_positive + self.false_negative
        return self.true_positive / total if total else 0.0


def _iou(box: tuple[float, float, float, float], detection: Detection) -> float:
    x1, y1 = max(box[0], detection.x1), max(box[1], detection.y1)
    x2, y2 = min(box[2], detection.x2), min(box[3], detection.y2)
    intersection = max(0.0, x2 - x1) * max(0.0, y2 - y1)
    box_area = (box[2] - box[0]) * (box[3] - box[1])
    detection_area = (detection.x2 - detection.x1) * (detection.y2 - detection.y1)
    union = box_area + detection_area - intersection
    return intersection / union if union > 0 else 0.0


def score_frame(
    detections: list[Detection],
    labelled_boxes: list[tuple[float, float, float, float]],
    *,
    iou_threshold: float = 0.5,
) -> DetectionScore:
    """Match each prediction to at most one labelled bovine box."""
    if not 0 < iou_threshold <= 1:
        raise ValueError("iou_threshold deve estar em (0, 1]")
    matched: set[int] = set()
    true_positive = 0
    for detection in sorted(detections, key=lambda item: item.confidence, reverse=True):
        candidates = [
            (_iou(box, detection), index)
            for index, box in enumerate(labelled_boxes)
            if index not in matched
        ]
        if not candidates:
            continue
        overlap, index = max(candidates)
        if overlap >= iou_threshold:
            matched.add(index)
            true_positive += 1
    return DetectionScore(
        true_positive, len(detections) - true_positive, len(labelled_boxes) - true_positive
    )
