from __future__ import annotations

from dataclasses import dataclass
from math import hypot

from fazenda_cv.domain import Detection, Track


@dataclass(slots=True)
class _TrackState:
    track_id: int
    center: tuple[float, float]
    confidence: float
    missed: int = 0


class CentroidTracker:
    """Small, deterministic tracker for a fixed, single-lane camera baseline."""

    def __init__(self, max_distance: float = 100.0, max_missed_frames: int = 12) -> None:
        self.max_distance = max_distance
        self.max_missed_frames = max_missed_frames
        self._next_id = 1
        self._tracks: dict[int, _TrackState] = {}

    @property
    def active_ids(self) -> set[int]:
        return set(self._tracks)

    def update(self, detections: list[Detection]) -> list[Track]:
        candidates = sorted(
            (
                hypot(state.center[0] - detection.center[0], state.center[1] - detection.center[1]),
                track_id,
                index,
            )
            for track_id, state in self._tracks.items()
            for index, detection in enumerate(detections)
        )
        assigned_tracks: set[int] = set()
        assigned_detections: set[int] = set()
        for distance, track_id, index in candidates:
            if distance > self.max_distance:
                break
            if track_id in assigned_tracks or index in assigned_detections:
                continue
            detection = detections[index]
            state = self._tracks[track_id]
            state.center = detection.center
            state.confidence = detection.confidence
            state.missed = 0
            assigned_tracks.add(track_id)
            assigned_detections.add(index)

        for track_id, state in list(self._tracks.items()):
            if track_id not in assigned_tracks:
                state.missed += 1
                if state.missed > self.max_missed_frames:
                    del self._tracks[track_id]

        for index, detection in enumerate(detections):
            if index in assigned_detections:
                continue
            track_id = self._next_id
            self._next_id += 1
            self._tracks[track_id] = _TrackState(track_id, detection.center, detection.confidence)

        return [
            Track(state.track_id, state.center, state.confidence)
            for state in self._tracks.values()
            if state.missed == 0
        ]
