from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, time
from enum import StrEnum
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo


class Direction(StrEnum):
    IN = "in"
    OUT = "out"


class EventType(StrEnum):
    PASSAGE = "passage"
    AFTER_HOURS = "after_hours"
    COUNT_MISMATCH = "count_mismatch"


def utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True, slots=True)
class Detection:
    x1: float
    y1: float
    x2: float
    y2: float
    confidence: float
    class_id: int

    @property
    def center(self) -> tuple[float, float]:
        return ((self.x1 + self.x2) / 2, (self.y1 + self.y2) / 2)


@dataclass(frozen=True, slots=True)
class Track:
    track_id: int
    center: tuple[float, float]
    confidence: float


@dataclass(frozen=True, slots=True)
class CountLine:
    # With this orientation, left-to-right is an inbound passage.
    start: tuple[float, float] = (0.5, 1.0)
    end: tuple[float, float] = (0.5, 0.0)

    def __post_init__(self) -> None:
        points = (*self.start, *self.end)
        if any(value < 0 or value > 1 for value in points):
            raise ValueError("Coordenadas da linha devem estar normalizadas entre 0 e 1")
        if self.start == self.end:
            raise ValueError("Os pontos inicial e final da linha precisam ser diferentes")

    def side(self, point: tuple[float, float], width: int, height: int) -> float:
        sx, sy = self.start[0] * width, self.start[1] * height
        ex, ey = self.end[0] * width, self.end[1] * height
        px, py = point
        return (ex - sx) * (py - sy) - (ey - sy) * (px - sx)


@dataclass(slots=True)
class MonitoringSession:
    expected_passages: int
    allowed_from: time
    allowed_until: time
    tolerance: int = 0
    session_id: str = field(default_factory=lambda: str(uuid4()))
    started_at: datetime = field(default_factory=utc_now)
    ended_at: datetime | None = None
    in_count: int = 0
    out_count: int = 0
    active: bool = True
    time_zone: str = "America/Sao_Paulo"

    @property
    def total_count(self) -> int:
        return self.in_count + self.out_count

    def is_allowed_time(self, moment: datetime) -> bool:
        current = moment.astimezone(ZoneInfo(self.time_zone)).time()
        if self.allowed_from <= self.allowed_until:
            return self.allowed_from <= current <= self.allowed_until
        return current >= self.allowed_from or current <= self.allowed_until


@dataclass(frozen=True, slots=True)
class MonitorEvent:
    event_type: EventType
    farm_id: str
    camera_id: str
    session_id: str
    occurred_at: datetime
    direction: Direction | None = None
    confidence: float | None = None
    model_version: str = "unknown"
    details: dict[str, Any] = field(default_factory=dict)
    event_id: str = field(default_factory=lambda: str(uuid4()))
    schema_version: int = 1

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["event_type"] = self.event_type.value
        result["direction"] = self.direction.value if self.direction else None
        result["occurred_at"] = self.occurred_at.isoformat()
        return result
