from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from uuid import uuid4


class Direction(StrEnum):
    IN = "in"
    OUT = "out"


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
    # A downward-to-upward line makes a left-to-right crossing an entry.
    start: tuple[float, float] = (0.5, 1.0)
    end: tuple[float, float] = (0.5, 0.0)

    def __post_init__(self) -> None:
        if any(not 0 <= value <= 1 for value in (*self.start, *self.end)):
            raise ValueError("As coordenadas da linha devem estar entre 0 e 1")
        if self.start == self.end:
            raise ValueError("A linha precisa de dois pontos diferentes")

    def side(self, point: tuple[float, float], width: int, height: int) -> float:
        sx, sy = self.start[0] * width, self.start[1] * height
        ex, ey = self.end[0] * width, self.end[1] * height
        px, py = point
        return (ex - sx) * (py - sy) - (ey - sy) * (px - sx)


@dataclass(frozen=True, slots=True)
class PassageEvent:
    source_id: str
    direction: Direction
    occurred_at: datetime
    confidence: float
    detector_version: str
    track_id: int
    session_id: str | None = None
    video_offset_ms: int | None = None
    time_basis: str = "live"
    event_id: str = field(default_factory=lambda: str(uuid4()))
    schema_version: int = 1

    def to_dict(self) -> dict[str, str | float | int]:
        result = asdict(self)
        result["direction"] = self.direction.value
        result["occurred_at"] = self.occurred_at.astimezone(UTC).isoformat()
        if self.session_id is None:
            result.pop("session_id")
        if self.video_offset_ms is None:
            result.pop("video_offset_ms")
        if self.time_basis == "live":
            result.pop("time_basis")
        return result
