import json

import pytest

from fazenda_cv.media_manifest import MediaRecord
from fazenda_cv.monitoring_annotations import load_monitoring_annotations


def catalog():
    return [
        MediaRecord(
            "clip_1",
            "video",
            "https://example.org/clip.mp4",
            "Author",
            "CC BY",
            "attribution",
            "a" * 64,
            "curral",
            "evaluation",
            10.0,
            25.0,
            640,
            480,
            "day",
            "none",
        )
    ]


def document():
    return {
        "boxes": [
            {
                "media_id": "clip_1",
                "frame_ms": 1000,
                "region_id": "area_a",
                "xyxy": [0.1, 0.2, 0.4, 0.6],
            }
        ],
        "episodes": [
            {
                "media_id": "clip_1",
                "kind": "crowding",
                "region_id": "area_a",
                "start_ms": 1000,
                "end_ms": 4000,
                "positive": True,
            },
            {
                "media_id": "clip_1",
                "kind": "outside_area",
                "region_id": "area_a",
                "start_ms": 5000,
                "end_ms": 7000,
                "positive": False,
            },
        ],
    }


def load(tmp_path, data):
    path = tmp_path / "labels.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return load_monitoring_annotations(path, catalog())


def test_load_monitoring_annotations_accepts_boxes_and_positive_negative_episodes(tmp_path):
    labels = load(tmp_path, document())
    assert labels.boxes[0].xyxy == (0.1, 0.2, 0.4, 0.6)
    assert [episode.positive for episode in labels.episodes] == [True, False]


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (lambda data: data["boxes"][0].update(xyxy=[0.5, 0.2, 0.4, 0.6]), "xyxy"),
        (lambda data: data["boxes"][0].update(frame_ms=11000), "frame_ms"),
        (lambda data: data["episodes"][0].update(end_ms=500), "Intervalo"),
        (lambda data: data["episodes"][0].update(kind="fall"), "Tipo"),
    ],
)
def test_load_monitoring_annotations_rejects_invalid_labels(tmp_path, change, message):
    data = document()
    change(data)
    with pytest.raises(ValueError, match=message):
        load(tmp_path, data)
