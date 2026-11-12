import csv

import pytest

from fazenda_cv.domain import Direction
from fazenda_cv.media_manifest import MediaRecord
from fazenda_cv.passage_annotations import FIELDS, load_passage_annotations


def media():
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


def write_labels(path, rows):
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def label(**changes):
    row = dict(
        media_id="clip_1",
        access_id="curral",
        video_offset_ms="1200",
        direction="in",
        ambiguous="false",
    )
    row.update(changes)
    return row


def test_load_passage_annotations(tmp_path):
    path = tmp_path / "passages.csv"
    write_labels(path, [label(), label(video_offset_ms="2400", direction="out", ambiguous="true")])
    annotations = load_passage_annotations(path, media())
    assert [item.direction for item in annotations] == [Direction.IN, Direction.OUT]
    assert annotations[1].ambiguous


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"media_id": "unknown"}, "vídeo não catalogado"),
        ({"video_offset_ms": "11000"}, "fora do vídeo"),
        ({"access_id": "outro"}, "acesso deve ser"),
        ({"direction": "?"}, "direção deve ser"),
    ],
)
def test_load_passage_annotations_rejects_bad_labels(tmp_path, changes, message):
    path = tmp_path / "passages.csv"
    write_labels(path, [label(**changes)])
    with pytest.raises(ValueError, match=message):
        load_passage_annotations(path, media())


def test_load_passage_annotations_rejects_duplicate(tmp_path):
    path = tmp_path / "passages.csv"
    write_labels(path, [label(), label()])
    with pytest.raises(ValueError, match="duplicada"):
        load_passage_annotations(path, media())
