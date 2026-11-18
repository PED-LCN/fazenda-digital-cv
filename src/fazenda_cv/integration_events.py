"""Versioned event envelope for future external consumers."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from uuid import uuid4

from fazenda_cv.domain import PassageEvent


class EventType(StrEnum):
    PASSAGE = "passage"
    OCCUPANCY = "occupancy"
    CROWDING = "crowding"
    IMMOBILITY = "immobility"
    BOUNDARY_EXIT = "boundary_exit"
    OUTSIDE_AREA = "outside_area"


REQUIRED_DATA = {
    EventType.PASSAGE: {"direction", "confidence", "detector_version", "track_id"},
    EventType.OCCUPANCY: {"count"},
    EventType.CROWDING: {"count", "threshold", "duration_ms"},
    EventType.IMMOBILITY: {"track_id", "duration_ms"},
    EventType.BOUNDARY_EXIT: {"track_id"},
    EventType.OUTSIDE_AREA: {"track_id"},
}


@dataclass(frozen=True, slots=True)
class IntegrationEvent:
    event_type: EventType
    source_id: str
    session_id: str
    occurred_at: datetime
    time_basis: str
    data: dict[str, str | int | float | bool]
    access_id: str | None = None
    area_id: str | None = None
    video_offset_ms: int | None = None
    event_id: str = field(default_factory=lambda: str(uuid4()))
    schema_version: int = 2

    def __post_init__(self) -> None:
        if not isinstance(self.event_type, EventType) or self.schema_version != 2:
            raise ValueError("Tipo ou versão de evento inválidos")
        if not self.source_id.strip() or not self.session_id.strip():
            raise ValueError("source_id e session_id são obrigatórios")
        if self.occurred_at.tzinfo is None or self.occurred_at.utcoffset() is None:
            raise ValueError("occurred_at exige fuso horário")
        if self.time_basis not in {"live", "replay"}:
            raise ValueError("time_basis deve ser live ou replay")
        if self.time_basis == "replay" and self.video_offset_ms is None:
            raise ValueError("replay exige video_offset_ms")
        if self.time_basis == "live" and self.video_offset_ms is not None:
            raise ValueError("fonte ao vivo não tem video_offset_ms")
        if self.video_offset_ms is not None and self.video_offset_ms < 0:
            raise ValueError("video_offset_ms não pode ser negativo")
        if self.event_type is EventType.PASSAGE:
            if not self.access_id or self.area_id:
                raise ValueError("passage exige apenas access_id")
        elif not self.area_id or self.access_id:
            raise ValueError("monitoramento exige apenas area_id")
        if set(self.data) != REQUIRED_DATA[self.event_type]:
            raise ValueError(f"Dados inválidos para {self.event_type.value}")
        if any(type(value) not in {str, int, float, bool} for value in self.data.values()):
            raise ValueError("data aceita apenas valores escalares")

    def to_dict(self) -> dict[str, object]:
        result = asdict(self)
        result["event_type"] = self.event_type.value
        result["occurred_at"] = self.occurred_at.astimezone(UTC).isoformat()
        if self.access_id is None:
            result.pop("access_id")
        if self.area_id is None:
            result.pop("area_id")
        if self.video_offset_ms is None:
            result.pop("video_offset_ms")
        return result


def passage_to_integration_event(
    passage: PassageEvent, *, access_id: str, session_id: str
) -> IntegrationEvent:
    """Wrap an existing passage while keeping its deduplication identifier."""
    return IntegrationEvent(
        event_type=EventType.PASSAGE,
        source_id=passage.source_id,
        session_id=passage.session_id or session_id,
        occurred_at=passage.occurred_at,
        time_basis=passage.time_basis,
        video_offset_ms=passage.video_offset_ms,
        access_id=access_id,
        data={
            "direction": passage.direction.value,
            "confidence": passage.confidence,
            "detector_version": passage.detector_version,
            "track_id": passage.track_id,
        },
        event_id=passage.event_id,
    )
