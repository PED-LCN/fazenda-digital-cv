import csv

import pytest

from fazenda_cv.media_manifest import FIELDS, load_manifest


def write_manifest(path, rows):
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def video_row(**changes):
    row = dict.fromkeys(FIELDS, "")
    row.update(
        media_id="curral_01",
        media_type="video",
        source_url="https://example.org/cattle.mp4",
        author="Autor do vídeo",
        license="CC BY 4.0",
        usage_terms="Atribuição obrigatória",
        sha256="a" * 64,
        environment="curral",
        split="tuning",
        duration_seconds="12.5",
        fps="25",
        width="1920",
        height="1080",
        lighting="dia",
        occlusion="parcial",
    )
    row.update(changes)
    return row


def test_load_manifest_accepts_video_and_photo(tmp_path):
    path = tmp_path / "manifest.csv"
    photo = video_row(
        media_id="foto_02",
        media_type="photo",
        sha256="b" * 64,
        split="evaluation",
        duration_seconds="",
        fps="",
    )
    write_manifest(path, [video_row(), photo])
    records = load_manifest(path)
    assert [record.media_type for record in records] == ["video", "photo"]
    assert records[0].duration_seconds == 12.5
    assert records[1].fps is None


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"license": ""}, "license é obrigatório"),
        ({"sha256": "bad"}, "sha256 inválido"),
        ({"duration_seconds": ""}, "vídeo exige duração"),
        ({"source_url": "rtsp://private"}, "source_url deve ser HTTP"),
    ],
)
def test_load_manifest_rejects_incomplete_media(tmp_path, changes, message):
    path = tmp_path / "manifest.csv"
    write_manifest(path, [video_row(**changes)])
    with pytest.raises(ValueError, match=message):
        load_manifest(path)


def test_load_manifest_rejects_same_media_in_both_splits(tmp_path):
    path = tmp_path / "manifest.csv"
    write_manifest(path, [video_row(), video_row(media_id="curral_02", split="evaluation")])
    with pytest.raises(ValueError, match="divisões diferentes"):
        load_manifest(path)
