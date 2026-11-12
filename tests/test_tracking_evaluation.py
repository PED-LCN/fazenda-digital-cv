import pytest

from fazenda_cv.domain import Track
from fazenda_cv.tracking_evaluation import LabelledPosition, score_tracks


def label(object_id, x):
    return LabelledPosition(object_id, (x, 20))


def track(track_id, x):
    return Track(track_id, (x, 20), 0.9)


def test_score_tracks_counts_switches_and_occlusion_fragments():
    frames = [
        ([label("cow-a", 10), label("cow-b", 40)], [track(1, 10), track(2, 40)]),
        ([label("cow-a", 15), label("cow-b", 45)], [track(2, 15), track(1, 45)]),
        ([label("cow-a", 20)], []),
        ([label("cow-a", 25)], [track(3, 25), track(9, 90)]),
    ]
    score = score_tracks(frames, max_distance=8)
    assert score.labelled_positions == 6
    assert score.missed_positions == 1
    assert score.identity_switches == 3
    assert score.fragments == 1
    assert score.false_tracks == 1
    assert score.recall == 5 / 6


def test_score_tracks_handles_empty_frames():
    score = score_tracks([([], [])], max_distance=10)
    assert score.labelled_positions == 0
    assert score.recall == 0


def test_score_tracks_rejects_duplicate_labels_and_distance():
    with pytest.raises(ValueError, match="max_distance"):
        score_tracks([], max_distance=0)
    with pytest.raises(ValueError, match="duplicado"):
        score_tracks([([label("a", 1), label("a", 2)], [])], max_distance=10)
