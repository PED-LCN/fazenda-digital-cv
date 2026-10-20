from __future__ import annotations

from datetime import UTC, datetime

from fazenda_cv.domain import (
    CountLine,
    Direction,
    EventType,
    MonitorEvent,
    MonitoringSession,
    Track,
)


class PassageCounter:
    def __init__(self, line: CountLine | None = None, debounce_seconds: float = 1.5) -> None:
        self.line = line or CountLine()
        self.debounce_seconds = debounce_seconds
        self._last_side: dict[int, int] = {}
        self._last_crossing: dict[int, datetime] = {}

    def retain_tracks(self, active_ids: set[int]) -> None:
        for track_id in set(self._last_side) - active_ids:
            self._last_side.pop(track_id, None)
            self._last_crossing.pop(track_id, None)

    def update(
        self,
        tracks: list[Track],
        frame_size: tuple[int, int],
        session: MonitoringSession,
        farm_id: str,
        camera_id: str,
        model_version: str,
        moment: datetime | None = None,
    ) -> list[MonitorEvent]:
        now = moment or datetime.now(UTC)
        width, height = frame_size
        events: list[MonitorEvent] = []
        for track in tracks:
            signed = self.line.side(track.center, width, height)
            side = 1 if signed >= 0 else -1
            old_side = self._last_side.get(track.track_id)
            self._last_side[track.track_id] = side
            if old_side is None or old_side == side:
                continue
            last_crossing = self._last_crossing.get(track.track_id)
            if last_crossing and (now - last_crossing).total_seconds() < self.debounce_seconds:
                continue
            self._last_crossing[track.track_id] = now
            direction = Direction.IN if old_side < side else Direction.OUT
            if direction is Direction.IN:
                session.in_count += 1
            else:
                session.out_count += 1
            events.append(
                MonitorEvent(
                    event_type=EventType.PASSAGE,
                    farm_id=farm_id,
                    camera_id=camera_id,
                    session_id=session.session_id,
                    occurred_at=now,
                    direction=direction,
                    confidence=track.confidence,
                    model_version=model_version,
                    details={"track_id": track.track_id},
                )
            )
            if not session.is_allowed_time(now):
                events.append(
                    MonitorEvent(
                        event_type=EventType.AFTER_HOURS,
                        farm_id=farm_id,
                        camera_id=camera_id,
                        session_id=session.session_id,
                        occurred_at=now,
                        direction=direction,
                        confidence=track.confidence,
                        model_version=model_version,
                        details={"track_id": track.track_id, "alert": True},
                    )
                )
        return events
