"""Camera-specific polygons used by the monitoring pipeline."""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import StrEnum
from math import isfinite
from pathlib import Path

import cv2
import numpy as np

Point = tuple[float, float]


class Location(StrEnum):
    INSIDE = "inside"
    BOUNDARY = "boundary"
    OUTSIDE = "outside"


def _cross(a: Point, b: Point, c: Point) -> float:
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _on_segment(point: Point, a: Point, b: Point) -> bool:
    return (
        abs(_cross(a, b, point)) < 1e-9
        and min(a[0], b[0]) - 1e-9 <= point[0] <= max(a[0], b[0]) + 1e-9
        and min(a[1], b[1]) - 1e-9 <= point[1] <= max(a[1], b[1]) + 1e-9
    )


def _intersects(a: Point, b: Point, c: Point, d: Point) -> bool:
    return (
        _on_segment(c, a, b)
        or _on_segment(d, a, b)
        or _on_segment(a, c, d)
        or _on_segment(b, c, d)
        or (_cross(a, b, c) * _cross(a, b, d) < 0 and _cross(c, d, a) * _cross(c, d, b) < 0)
    )


@dataclass(frozen=True, slots=True)
class NormalizedPolygon:
    vertices: tuple[Point, ...]

    def __post_init__(self) -> None:
        points = self.vertices
        if len(points) < 3 or len(set(points)) != len(points):
            raise ValueError("Polígono exige ao menos três vértices distintos")
        if any(not isfinite(value) or not 0 <= value <= 1 for point in points for value in point):
            raise ValueError("Coordenadas do polígono devem estar entre 0 e 1")
        area_twice = sum(
            points[i][0] * points[(i + 1) % len(points)][1]
            - points[(i + 1) % len(points)][0] * points[i][1]
            for i in range(len(points))
        )
        if abs(area_twice) < 1e-9:
            raise ValueError("Polígono precisa ter área positiva")
        for i in range(len(points)):
            for j in range(i + 1, len(points)):
                if j in {i, (i + 1) % len(points)} or i == (j + 1) % len(points):
                    continue
                if _intersects(
                    points[i],
                    points[(i + 1) % len(points)],
                    points[j],
                    points[(j + 1) % len(points)],
                ):
                    raise ValueError("Polígono não pode cruzar a si mesmo")

    def locate(self, point: Point) -> Location:
        """Return inside, boundary, or outside for a normalized point."""
        x, y = point
        if not isfinite(x) or not isfinite(y):
            raise ValueError("Ponto inválido")
        inside = False
        for index, a in enumerate(self.vertices):
            b = self.vertices[(index + 1) % len(self.vertices)]
            if _on_segment(point, a, b):
                return Location.BOUNDARY
            if (a[1] > y) != (b[1] > y):
                crossing_x = a[0] + (y - a[1]) * (b[0] - a[0]) / (b[1] - a[1])
                if crossing_x > x:
                    inside = not inside
        return Location.INSIDE if inside else Location.OUTSIDE


@dataclass(frozen=True, slots=True)
class MonitoringArea:
    source_id: str
    authorized_area: NormalizedPolygon
    regions: dict[str, NormalizedPolygon]


def _polygon(value: object) -> NormalizedPolygon:
    if not isinstance(value, list):
        raise ValueError("Polígono deve ser lista de pontos")
    points: list[Point] = []
    for raw in value:
        if (
            not isinstance(raw, list)
            or len(raw) != 2
            or any(type(item) not in {int, float} for item in raw)
        ):
            raise ValueError("Cada ponto exige duas coordenadas numéricas")
        points.append((float(raw[0]), float(raw[1])))
    return NormalizedPolygon(tuple(points))


def load_areas(path: str | Path) -> dict[str, MonitoringArea]:
    """Load authorized and observed regions for independent camera sources."""
    with Path(path).open(encoding="utf-8") as file:
        document = json.load(file)
    if not isinstance(document, dict) or set(document) != {"sources"}:
        raise ValueError("Configuração exige a chave sources")
    if not isinstance(document["sources"], list) or not document["sources"]:
        raise ValueError("Configure ao menos uma fonte")
    sources = {}
    for item in document["sources"]:
        if not isinstance(item, dict) or set(item) != {"source_id", "authorized_area", "regions"}:
            raise ValueError("Fonte exige source_id, authorized_area e regions")
        source_id = item["source_id"]
        if not isinstance(source_id, str) or not source_id.strip() or source_id in sources:
            raise ValueError("source_id inválido ou duplicado")
        authorized = _polygon(item["authorized_area"])
        if not isinstance(item["regions"], list):
            raise ValueError("regions deve ser uma lista")
        regions = {}
        for region in item["regions"]:
            if not isinstance(region, dict) or set(region) != {"region_id", "polygon"}:
                raise ValueError("Região exige region_id e polygon")
            region_id = region["region_id"]
            if not isinstance(region_id, str) or not region_id.strip() or region_id in regions:
                raise ValueError("region_id inválido ou duplicado")
            regions[region_id] = _polygon(region["polygon"])
        sources[source_id] = MonitoringArea(source_id, authorized, regions)
    return sources


def annotate_areas(frame: np.ndarray, area: MonitoringArea) -> np.ndarray:
    """Overlay the authorized boundary and named observation regions."""
    image = frame.copy()
    height, width = image.shape[:2]
    for name, polygon, color in [
        ("curral", area.authorized_area, (0, 220, 255)),
        *((region_id, polygon, (255, 200, 0)) for region_id, polygon in area.regions.items()),
    ]:
        points = np.array(
            [(round(x * (width - 1)), round(y * (height - 1))) for x, y in polygon.vertices],
            dtype=np.int32,
        )
        cv2.polylines(image, [points], True, color, 2)
        cv2.putText(image, name, tuple(points[0]), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 1)
    return image
