from datetime import UTC, datetime

import pytest

from fazenda_cv.domain import Direction, PassageEvent
from fazenda_cv.integration_events import (
    EventType,
    IntegrationEvent,
    passage_to_integration_event,
)


def passage():
    return PassageEvent(
        "camera-a",
        Direction.IN,
        datetime(2026, 11, 12, tzinfo=UTC),
        0.8,
        "model-x",
        3,
        session_id="session-a",
        video_offset_ms=1200,
        time_basis="replay",
        event_id="event-a",
    )


def test_wrap_passage_keeps_event_id_and_v1_output():
    old = passage()
    event = passage_to_integration_event(old, access_id="curral", session_id="fallback")
    payload = event.to_dict()
    assert payload["schema_version"] == 2
    assert payload["event_type"] == "passage"
    assert payload["access_id"] == "curral"
    assert payload["session_id"] == "session-a"
    assert payload["video_offset_ms"] == 1200
    assert payload["event_id"] == old.to_dict()["event_id"]
    assert old.to_dict()["schema_version"] == 1


def test_occupancy_has_area_and_no_access():
    event = IntegrationEvent(
        EventType.OCCUPANCY,
        "camera-a",
        "session-a",
        datetime.now(UTC),
        "live",
        {"count": 5},
        area_id="curral",
    )
    payload = event.to_dict()
    assert payload["area_id"] == "curral"
    assert "access_id" not in payload
    assert "video_offset_ms" not in payload


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"video_offset_ms": None}, "replay exige"),
        ({"access_id": None}, "passage exige"),
        ({"data": {"direction": "in"}}, "Dados inválidos"),
    ],
)
def test_event_rejects_incomplete_payload(changes, message):
    args = dict(
        event_type=EventType.PASSAGE,
        source_id="camera-a",
        session_id="session-a",
        occurred_at=datetime.now(UTC),
        time_basis="replay",
        video_offset_ms=1200,
        access_id="curral",
        data={"direction": "in", "confidence": 0.8, "detector_version": "x", "track_id": 1},
    )
    args.update(changes)
    with pytest.raises(ValueError, match=message):
        IntegrationEvent(**args)
