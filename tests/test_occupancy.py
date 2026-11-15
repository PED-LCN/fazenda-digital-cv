from datetime import UTC, datetime

import pytest

from fazenda_cv.areas import MonitoringArea, NormalizedPolygon
from fazenda_cv.domain import Detection
from fazenda_cv.occupancy import measure_occupancy


def test_centers_include_boundary_and_overlapping_regions_with_video_reference():
    polygon = NormalizedPolygon(((0, 0), (0.5, 0), (0.5, 1), (0, 1)))
    area = MonitoringArea("cam", polygon, {"a": polygon, "b": polygon})
    boxes = [Detection(40, 40, 60, 60, 0.8, 19), Detection(70, 70, 90, 90, 0.8, 19)]
    events = measure_occupancy(
        boxes,
        area,
        (100, 100),
        session_id="s",
        occurred_at=datetime.now(UTC),
        time_basis="replay",
        video_offset_ms=1000,
    )
    assert [e.data["count"] for e in events] == [1, 1]
    assert [e.area_id for e in events] == ["a", "b"]
    assert all(e.video_offset_ms == 1000 and e.session_id == "s" for e in events)
    assert events[0].event_id != events[1].event_id
    empty = measure_occupancy(
        [],
        area,
        (100, 100),
        session_id="s",
        occurred_at=datetime.now(UTC),
        time_basis="replay",
        video_offset_ms=2000,
    )
    assert all(e.data["count"] == 0 for e in empty)
    with pytest.raises(ValueError):
        measure_occupancy(
            [],
            area,
            (0, 100),
            session_id="s",
            occurred_at=datetime.now(UTC),
            time_basis="live",
            video_offset_ms=None,
        )
