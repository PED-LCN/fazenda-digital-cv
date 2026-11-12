"""Identity continuity measurements for a tracking adapter."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from math import hypot

from fazenda_cv.domain import Track


@dataclass(frozen=True, slots=True)
class LabelledPosition:
    object_id: str
    center: tuple[float, float]


@dataclass(frozen=True, slots=True)
class TrackingScore:
    labelled_positions: int
    missed_positions: int
    false_tracks: int
    identity_switches: int
    fragments: int

    @property
    def recall(self) -> float:
        return (
            (self.labelled_positions - self.missed_positions) / self.labelled_positions
            if self.labelled_positions
            else 0.0
        )


def score_tracks(
    frames: Iterable[tuple[list[LabelledPosition], list[Track]]],
    *,
    max_distance: float,
) -> TrackingScore:
    """Match tracks to labelled animals per frame and count continuity failures."""
    if max_distance <= 0:
        raise ValueError("max_distance deve ser positivo")
    previous_id: dict[str, int] = {}
    missing_since_seen: set[str] = set()
    labelled_positions = missed = false_tracks = switches = fragments = 0
    for labels, tracks in frames:
        label_ids = [label.object_id for label in labels]
        if len(label_ids) != len(set(label_ids)):
            raise ValueError("object_id duplicado no quadro")
        candidates = sorted(
            (
                hypot(label.center[0] - track.center[0], label.center[1] - track.center[1]),
                label_index,
                track_index,
            )
            for label_index, label in enumerate(labels)
            for track_index, track in enumerate(tracks)
        )
        assigned_labels: set[int] = set()
        assigned_tracks: set[int] = set()
        for distance, label_index, track_index in candidates:
            if distance > max_distance:
                break
            if label_index in assigned_labels or track_index in assigned_tracks:
                continue
            label = labels[label_index]
            track = tracks[track_index]
            old_id = previous_id.get(label.object_id)
            if old_id is not None and old_id != track.track_id:
                switches += 1
            if label.object_id in missing_since_seen:
                fragments += 1
                missing_since_seen.remove(label.object_id)
            previous_id[label.object_id] = track.track_id
            assigned_labels.add(label_index)
            assigned_tracks.add(track_index)
        labelled_positions += len(labels)
        missed += len(labels) - len(assigned_labels)
        false_tracks += len(tracks) - len(assigned_tracks)
        for index, label in enumerate(labels):
            if index not in assigned_labels and label.object_id in previous_id:
                missing_since_seen.add(label.object_id)
    return TrackingScore(labelled_positions, missed, false_tracks, switches, fragments)
