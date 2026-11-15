"""Cow Tracking's per-frame normalized boxes: class column denotes animal ID."""

from __future__ import annotations

from math import isfinite
from pathlib import Path

from fazenda_cv.mot_boxes import MotBox


def read_cattle_frame(path: Path, frame: int, width: int, height: int) -> list[MotBox]:
    result = []
    seen = set()
    for row in path.read_text().splitlines():
        if not row.strip():
            continue
        columns = row.split()
        if len(columns) != 5:
            raise ValueError(f"Rótulo exige ID e quatro coordenadas: {path.name}")
        identity = int(columns[0])
        cx, cy, w, h = map(float, columns[1:])
        if (
            identity < 0
            or identity in seen
            or not all(isfinite(x) for x in (cx, cy, w, h))
            or not all(0 <= x <= 1 for x in (cx, cy))
            or not 0 < w <= 1
            or not 0 < h <= 1
        ):
            raise ValueError(f"Caixa/ID inválido: {path.name}")
        seen.add(identity)
        result.append(
            MotBox(
                frame,
                identity,
                (
                    (cx - w / 2) * width,
                    (cy - h / 2) * height,
                    (cx + w / 2) * width,
                    (cy + h / 2) * height,
                ),
            )
        )
    return result
