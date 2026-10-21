from __future__ import annotations

from datetime import UTC, datetime

from fazenda_cv.domain import CountLine, Direction, PassageEvent, Track


class PassageCounter:
    """Emits a passage when a tracked object's center changes sides of the line."""

    def __init__(self, line: CountLine | None = None, debounce_seconds: float = 1.5) -> None:
        self.line = line or CountLine()
        self.debounce_seconds = debounce_seconds
        self.in_count = 0
        self.out_count = 0
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
        source_id: str,
        detector_version: str,
        moment: datetime | None = None,
    ) -> list[PassageEvent]:
        now = moment or datetime.now(UTC)
        width, height = frame_size
        events: list[PassageEvent] = []
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
                self.in_count += 1
            else:
                self.out_count += 1
            events.append(
                PassageEvent(
                    source_id=source_id,
                    direction=direction,
                    occurred_at=now,
                    confidence=track.confidence,
                    detector_version=detector_version,
                    track_id=track.track_id,
                )
            )
        return events
