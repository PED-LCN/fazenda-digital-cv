import pytest

from fazenda_cv.mot_data import aligned_mot_frames, read_mot_positions
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
