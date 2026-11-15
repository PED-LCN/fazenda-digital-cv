import pytest

from fazenda_cv.mot_data import (
    aligned_mot_frames,
    read_mot_positions,
    replay_mot_labels_as_detections,
)
from fazenda_cv.tracking import CentroidTracker
from fazenda_cv.tracking_evaluation import score_tracks


def test_read_mot_positions_and_align_missing_frames():
    labels = read_mot_positions(
        [
            "1,3,10,20,4,6,1,-1,-1,-1\n",
            "2,3,12,20,4,6,1,-1,-1,-1\n",
            "3,3,14,20,4,6,0,-1,-1,-1\n",
        ]
    )
    predictions = read_mot_positions(["1,8,11,20,4,6,0.8,-1,-1,-1\n"])

    frames = list(aligned_mot_frames(labels, predictions, first_frame=1, last_frame=3))

    assert frames[0][0][0].center == (12, 23)
    assert frames[0][1][0].track_id == 8
    assert frames[1][1] == []
    assert frames[2] == ([], [])
    score = score_tracks(frames, max_distance=5)
    assert score.labelled_positions == 2
    assert score.missed_positions == 1


@pytest.mark.parametrize(
    "row",
    [
        "1,2,0,0,1,1\n",
        "0,2,0,0,1,1,1\n",
        "1,-1,0,0,1,1,1\n",
        "1,2,0,0,-1,1,1\n",
        "1,2,nan,0,1,1,1\n",
        "1,2,0,0,1,1,1.5\n",
    ],
)
def test_rejects_invalid_mot_row(row):
    with pytest.raises(ValueError):
        read_mot_positions([row])


def test_rejects_duplicate_id_and_invalid_range():
    row = "1,2,0,0,1,1,1\n"
    with pytest.raises(ValueError, match="duplicado"):
        read_mot_positions([row, row])
    with pytest.raises(ValueError, match="Intervalo"):
        read_mot_positions([row], first_frame=2, last_frame=1)


def test_accepts_zero_based_cattle_id():
    frames = read_mot_positions(["1,0,0,0,2,2,1\n"])
    assert frames[1][0].object_id == 0


def test_scales_centers_for_decoded_video():
    frames = read_mot_positions(["1,3,528,328,146,82,1\n"], coordinate_scale=2)
    assert frames[1][0].center == (1202, 738)
    with pytest.raises(ValueError, match="coordinate_scale"):
        read_mot_positions([], coordinate_scale=0)


def test_replay_measures_tracker_without_using_ground_truth_ids():
    labels = read_mot_positions(
        [
            "1,90,0,0,2,2,1\n",
            "1,17,20,0,2,2,1\n",
            "2,90,20,0,2,2,1\n",
            "2,17,0,0,2,2,1\n",
        ]
    )
    tracker = CentroidTracker(max_distance=25)

    frames = list(replay_mot_labels_as_detections(labels, tracker, first_frame=1, last_frame=3))

    assert [item.object_id for item in frames[0][0]] == ["90", "17"]
    assert [item.track_id for item in frames[0][1]] == [1, 2]
    assert frames[2] == ([], [])
    score = score_tracks(frames, max_distance=5)
    assert score.identity_switches == 2
    assert score.missed_positions == 0


def test_replay_rejects_invalid_frame_interval():
    with pytest.raises(ValueError, match="Intervalo"):
        list(replay_mot_labels_as_detections({}, CentroidTracker(), first_frame=0, last_frame=1))
