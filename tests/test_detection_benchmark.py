import pytest

from fazenda_cv.detection_benchmark import FrameObservation, combine_scores, score_sequence
from fazenda_cv.domain import Detection
from fazenda_cv.mot_boxes import MotBox


def frame(number, hit=True, duplicate=False):
    labels = [MotBox(number, 1, (0, 0, 10, 10)), MotBox(number, 2, (20, 0, 30, 10))]
    boxes = [Detection(0, 0, 10, 10, 0.9, 19)] if hit else []
    return FrameObservation(number, labels, boxes * (2 if duplicate else 1))


def test_retention_does_not_hide_never_detected_animals_or_duplicate_boxes():
    result = score_sequence([frame(1, duplicate=True), frame(2), frame(3, False), frame(4)])
    assert result["true_positive"] == 3
    assert result["false_positive"] == 1
    assert result["false_negative"] == 5
    assert result["retention"] == pytest.approx(2 / 3)
    assert result["consecutive_retention"] == 0.5
    assert result["acquired_tracks"] == 1
    assert result["labelled_tracks"] == 2
    assert result["tracks"][1]["retention"] is None
    assert not combine_scores([result])["target_met"]


def test_last_frame_acquisition_has_no_retention_evidence():
    result = score_sequence([frame(1, False), frame(2)])
    assert result["retention"] is None
    assert not combine_scores([result])["target_met"]


def test_absent_observations_are_not_carried_forward():
    result = score_sequence([frame(1), frame(2, False), frame(3, False)])
    assert result["retention"] == 0
    with pytest.raises(ValueError):
        score_sequence([frame(2), frame(1)])


def test_aggregation_uses_opportunities_not_mean_of_percentages():
    a = score_sequence([frame(1), frame(2)])
    b = score_sequence([frame(1), frame(2, False), frame(3, False), frame(4, False)])
    assert combine_scores([a, b])["retention"] == 0.25


def test_two_of_three_detected_continuously_meets_targets_but_reports_coverage():
    observations = []
    for n in range(1, 5):
        labels = [MotBox(n, i, (i * 20, 0, i * 20 + 10, 10)) for i in range(3)]
        detections = [Detection(i * 20, 0, i * 20 + 10, 10, 0.8, 19) for i in range(2)]
        observations.append(FrameObservation(n, labels, detections))
    score = combine_scores([score_sequence(observations)])
    assert score["recall"] == pytest.approx(2 / 3)
    assert score["retention"] == 1
    assert score["acquired_tracks"] == 2
    assert score["labelled_tracks"] == 3
    assert score["target_met"]
