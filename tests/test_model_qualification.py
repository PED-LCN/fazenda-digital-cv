import hashlib

import pytest

from fazenda_cv.domain import Detection
from fazenda_cv.model_qualification import load_model_card, score_frame


def test_load_model_card_verifies_hash_and_classes(tmp_path):
    model = tmp_path / "weights.onnx"
    model.write_bytes(b"synthetic model bytes")
    digest = hashlib.sha256(model.read_bytes()).hexdigest()
    card = tmp_path / "model.toml"
    card.write_text(
        f'path = "weights.onnx"\nsource_url = "https://example.org/model"\n'
        f'license = "Apache-2.0"\nsha256 = "{digest}"\ninput_size = 416\n'
        'cattle_class_id = 1\nclass_names = ["other", "cow"]\n',
        encoding="utf-8",
    )
    loaded = load_model_card(card)
    assert loaded.sha256 == digest
    assert loaded.cattle_class_id == 1
    model.write_bytes(b"changed")
    with pytest.raises(ValueError, match="SHA-256"):
        load_model_card(card)


def test_score_frame_counts_matches_duplicates_and_misses():
    boxes = [(0, 0, 10, 10), (30, 0, 40, 10)]
    detections = [
        Detection(0, 0, 10, 10, 0.9, 19),
        Detection(0, 0, 10, 10, 0.7, 19),
    ]
    score = score_frame(detections, boxes)
    assert (score.true_positive, score.false_positive, score.false_negative) == (1, 1, 1)
    assert score.precision == 0.5
    assert score.recall == 0.5


def test_score_frame_rejects_invalid_threshold():
    with pytest.raises(ValueError, match="iou_threshold"):
        score_frame([], [], iou_threshold=0)
