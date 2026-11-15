"""Read MOTChallenge box annotations for tracking evaluation."""

from __future__ import annotations

import csv
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from math import isfinite

from fazenda_cv.domain import Detection, Track
from fazenda_cv.tracking import CentroidTracker
from fazenda_cv.tracking_evaluation import LabelledPosition


@dataclass(frozen=True, slots=True)
class MotPosition:
    frame: int
    object_id: int
    center: tuple[float, float]
    confidence: float


def read_mot_positions(
    lines: Iterable[str],
    *,
    first_frame: int = 1,
    last_frame: int | None = None,
    coordinate_scale: float = 1.0,
) -> dict[int, list[MotPosition]]:
    """Read one-indexed MOT rows: frame, ID, x, y, width, height, confidence, ..."""
    if first_frame < 1 or (last_frame is not None and last_frame < first_frame):
        raise ValueError("Intervalo de quadros inválido")
    if not isfinite(coordinate_scale) or coordinate_scale <= 0:
        raise ValueError("coordinate_scale deve ser positivo")
    frames: dict[int, list[MotPosition]] = defaultdict(list)
    seen: set[tuple[int, int]] = set()
    for row_number, row in enumerate(csv.reader(lines), start=1):
        if not row or all(not cell.strip() for cell in row):
            continue
        if len(row) < 7:
            raise ValueError(f"Linha MOT {row_number}: esperadas ao menos 7 colunas")
        try:
            frame, object_id = int(row[0]), int(row[1])
            x, y, width, height, confidence = (float(value) for value in row[2:7])
        except ValueError as error:
            raise ValueError(f"Linha MOT {row_number}: valor não numérico") from error
        if (
            frame < 1
            or object_id < 0
            or any(not isfinite(value) for value in (x, y, width, height, confidence))
            or width <= 0
            or height <= 0
            or not 0 <= confidence <= 1
        ):
            raise ValueError(f"Linha MOT {row_number}: posição ou confiança inválida")
        if frame < first_frame or (last_frame is not None and frame > last_frame):
            continue
        key = (frame, object_id)
        if key in seen:
            raise ValueError(f"Linha MOT {row_number}: ID duplicado no quadro")
        seen.add(key)
        if confidence == 0:
            continue
        frames[frame].append(
            MotPosition(
                frame,
                object_id,
                ((x + width / 2) * coordinate_scale, (y + height / 2) * coordinate_scale),
                confidence,
            )
        )
    return dict(frames)


def aligned_mot_frames(
    ground_truth: dict[int, list[MotPosition]],
    predictions: dict[int, list[MotPosition]],
    *,
    first_frame: int,
    last_frame: int,
) -> Iterable[tuple[list[LabelledPosition], list[Track]]]:
    """Align ground truth and predictions, preserving empty and missed frames."""
    if first_frame < 1 or last_frame < first_frame:
        raise ValueError("Intervalo de quadros inválido")
    for frame in range(first_frame, last_frame + 1):
        labels = [
            LabelledPosition(str(item.object_id), item.center)
            for item in ground_truth.get(frame, [])
        ]
        tracks = [
            Track(item.object_id, item.center, item.confidence)
            for item in predictions.get(frame, [])
        ]
        yield labels, tracks


def replay_mot_labels_as_detections(
    ground_truth: dict[int, list[MotPosition]],
    tracker: CentroidTracker,
    *,
    first_frame: int,
    last_frame: int,
) -> Iterable[tuple[list[LabelledPosition], list[Track]]]:
    """Measure association alone by feeding labelled centers without their IDs.

    This is an ideal-detection experiment, not a detector or end-to-end score.
    Create a fresh tracker for each independent sequence or interval.
    """
    if first_frame < 1 or last_frame < first_frame:
        raise ValueError("Intervalo de quadros inválido")
    for frame in range(first_frame, last_frame + 1):
        positions = ground_truth.get(frame, [])
        labels = [LabelledPosition(str(item.object_id), item.center) for item in positions]
        detections = [
            Detection(item.center[0], item.center[1], item.center[0], item.center[1], 1.0, 19)
            for item in positions
        ]
        yield labels, tracker.update(detections)
