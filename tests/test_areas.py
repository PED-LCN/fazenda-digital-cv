import json

import cv2
import numpy as np
import pytest

from fazenda_cv.__main__ import main
from fazenda_cv.areas import Location, NormalizedPolygon, annotate_areas, load_areas

SQUARE = [[0.1, 0.1], [0.9, 0.1], [0.9, 0.9], [0.1, 0.9]]


def area_config(*, source_id="curral-1", polygon=None):
    return {
        "sources": [
            {
                "source_id": source_id,
                "authorized_area": SQUARE if polygon is None else polygon,
                "regions": [
                    {"region_id": "bebedouro", "polygon": [[0.2, 0.2], [0.4, 0.2], [0.3, 0.4]]}
                ],
            }
        ]
    }


def test_load_areas_and_locate_points(tmp_path):
    path = tmp_path / "areas.json"
    path.write_text(json.dumps(area_config()), encoding="utf-8")

    area = load_areas(path)["curral-1"]

    assert area.authorized_area.locate((0.5, 0.5)) == Location.INSIDE
    assert area.authorized_area.locate((0.05, 0.5)) == Location.OUTSIDE
    assert area.authorized_area.locate((0.1, 0.5)) == Location.BOUNDARY
    assert area.regions["bebedouro"].locate((0.3, 0.3)) == Location.INSIDE


@pytest.mark.parametrize(
    "polygon",
    [
        [[0.1, 0.1], [0.9, 0.1]],
        [[0.1, 0.1], [0.9, 0.1], [1.1, 0.9]],
        [[0.1, 0.1], [0.9, 0.9], [0.1, 0.9], [0.9, 0.1]],
        [[0.1, 0.1], [0.5, 0.5], [0.9, 0.9]],
    ],
)
def test_rejects_invalid_polygon(polygon):
    with pytest.raises(ValueError):
        NormalizedPolygon(tuple(map(tuple, polygon)))


def test_rejects_duplicate_sources_and_regions(tmp_path):
    path = tmp_path / "areas.json"
    config = area_config()
    config["sources"].append(config["sources"][0])
    path.write_text(json.dumps(config), encoding="utf-8")
    with pytest.raises(ValueError, match="source_id"):
        load_areas(path)

    config["sources"].pop()
    config["sources"][0]["regions"] *= 2
    path.write_text(json.dumps(config), encoding="utf-8")
    with pytest.raises(ValueError, match="region_id"):
        load_areas(path)


def test_overlay_draws_boundaries_without_mutating_frame(tmp_path):
    path = tmp_path / "areas.json"
    path.write_text(json.dumps(area_config()), encoding="utf-8")
    frame = np.zeros((100, 100, 3), dtype=np.uint8)

    annotated = annotate_areas(frame, load_areas(path)["curral-1"])

    assert annotated.sum() > 0
    assert frame.sum() == 0
    assert annotated[10, 50].any()


def test_cli_writes_area_overlay_to_annotated_video(tmp_path):
    config = tmp_path / "areas.json"
    config.write_text(json.dumps(area_config()), encoding="utf-8")
    video = tmp_path / "empty.avi"
    writer = cv2.VideoWriter(str(video), cv2.VideoWriter_fourcc(*"MJPG"), 10, (100, 100))
    assert writer.isOpened()
    writer.write(np.zeros((100, 100, 3), dtype=np.uint8))
    writer.release()
    output = tmp_path / "annotated.avi"

    assert (
        main(
            [
                "--source",
                str(video),
                "--simulator",
                "--source-id",
                "curral-1",
                "--areas-config",
                str(config),
                "--annotated",
                str(output),
            ]
        )
        == 0
    )

    capture = cv2.VideoCapture(str(output))
    ok, frame = capture.read()
    capture.release()
    assert ok
    assert frame[10, 50].any()


def test_cli_rejects_missing_source_in_area_config(tmp_path):
    config = tmp_path / "areas.json"
    config.write_text(json.dumps(area_config()), encoding="utf-8")
    with pytest.raises(SystemExit, match="2"):
        main(
            [
                "--source",
                str(tmp_path / "unused.avi"),
                "--simulator",
                "--source-id",
                "ordenha-1",
                "--areas-config",
                str(config),
            ]
        )
