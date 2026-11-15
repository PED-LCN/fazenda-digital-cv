"""Read MOTChallenge cattle boxes for frame-aligned detector evaluation."""

from __future__ import annotations

import csv
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True, slots=True)
class MotBox:
    frame: int
    object_id: int
    xyxy: tuple[float, float, float, float]


def read_mot_boxes(
    lines: Iterable[str],
    *,
    coordinate_scale: float = 1.0,
    first_frame: int = 1,
    last_frame: int | None = None,
) -> dict[int, list[MotBox]]:
    """Read one-indexed MOT rows, scaling boxes into the decoded video's pixels."""
    if not isfinite(coordinate_scale) or coordinate_scale <= 0:
        raise ValueError("coordinate_scale deve ser positivo")
    if first_frame < 1 or (last_frame is not None and last_frame < first_frame):
        raise ValueError("Intervalo de quadros inválido")
    frames: dict[int, list[MotBox]] = defaultdict(list)
    seen: set[tuple[int, int]] = set()
    for line_number, row in enumerate(csv.reader(lines), start=1):
        if not row or all(not value.strip() for value in row):
            continue
        if len(row) < 7:
            raise ValueError(f"Linha MOT {line_number}: esperadas 7 colunas")
        try:
            frame, object_id = int(row[0]), int(row[1])
            x, y, width, height, confidence = (float(value) for value in row[2:7])
        except ValueError as error:
            raise ValueError(f"Linha MOT {line_number}: valor não numérico") from error
        if (
            frame < 1
            or object_id < 0
            or any(not isfinite(value) for value in (x, y, width, height, confidence))
            or x < 0
            or y < 0
            or width <= 0
            or height <= 0
            or not 0 <= confidence <= 1
        ):
            raise ValueError(f"Linha MOT {line_number}: caixa inválida")
        if frame < first_frame or (last_frame is not None and frame > last_frame):
            continue
        key = (frame, object_id)
        if key in seen:
            raise ValueError(f"Linha MOT {line_number}: ID duplicado no quadro")
        seen.add(key)
        if confidence == 0:
            continue
        frames[frame].append(
            MotBox(
                frame,
                object_id,
                (
                    x * coordinate_scale,
                    y * coordinate_scale,
                    (x + width) * coordinate_scale,
                    (y + height) * coordinate_scale,
                ),
            )
        )
    return dict(frames)
