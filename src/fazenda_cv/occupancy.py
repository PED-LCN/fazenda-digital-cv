"""Per-region occupancy estimates from detection centers."""

from __future__ import annotations

from datetime import datetime

from fazenda_cv.areas import Location, MonitoringArea
from fazenda_cv.domain import Detection
from fazenda_cv.integration_events import EventType, IntegrationEvent


def measure_occupancy(
    detections: list[Detection],
    area: MonitoringArea,
    image_size: tuple[int, int],
    *,
    session_id: str,
    occurred_at: datetime,
    time_basis: str,
    video_offset_ms: int | None,
) -> list[IntegrationEvent]:
    width, height = image_size
    if width <= 0 or height <= 0:
        raise ValueError("Dimensões da imagem devem ser positivas")
    centers = [(d.center[0] / width, d.center[1] / height) for d in detections]
    return [
        IntegrationEvent(
            EventType.OCCUPANCY,
            area.source_id,
            session_id,
            occurred_at,
            time_basis,
            {"count": sum(polygon.locate(center) != Location.OUTSIDE for center in centers)},
            area_id=region,
            video_offset_ms=video_offset_ms,
        )
        for region, polygon in area.regions.items()
    ]
