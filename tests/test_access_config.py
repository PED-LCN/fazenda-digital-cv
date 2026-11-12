import json

import numpy as np
import pytest

from fazenda_cv.access_config import load_access_configs
from fazenda_cv.pipeline import CvPipeline


def document():
    return {
        "accesses": [
            {"access_id": "curral", "source_id": "camera-a", "line": [0.5, 1, 0.5, 0]},
            {"access_id": "ordenha", "source_id": "camera-b", "line": [0.25, 0, 0.25, 1]},
        ]
    }


def write_config(path, data):
    path.write_text(json.dumps(data), encoding="utf-8")


def test_load_access_configs_keeps_sources_and_directions_independent(tmp_path):
    path = tmp_path / "accesses.json"
    write_config(path, document())
    configs = load_access_configs(path)
    assert configs["curral"].source_id == "camera-a"
    assert configs["ordenha"].source_id == "camera-b"
    assert configs["curral"].line.side((75, 50), 100, 100) > 0
    assert configs["ordenha"].line.side((75, 50), 100, 100) < 0


@pytest.mark.parametrize(
    "change",
    [
        lambda data: data["accesses"].pop(),
        lambda data: data["accesses"][1].update(access_id="curral"),
        lambda data: data["accesses"][0].update(line=[0.5, 0.5, 0.5, 0.5]),
        lambda data: data["accesses"][0].update(source_id=""),
    ],
)
def test_load_access_configs_rejects_invalid_configuration(tmp_path, change):
    data = document()
    change(data)
    path = tmp_path / "accesses.json"
    write_config(path, data)
    with pytest.raises(ValueError):
        load_access_configs(path)


def test_annotation_draws_entry_direction(tmp_path):
    path = tmp_path / "accesses.json"
    write_config(path, document())
    line = load_access_configs(path)["curral"].line

    class EmptyDetector:
        model_version = "test"

        def detect(self, frame):
            return []

    pipeline = CvPipeline(EmptyDetector(), "camera-a", line)
    frame = np.zeros((100, 100, 3), dtype=np.uint8)
    result = pipeline.process(frame)
    annotated = pipeline.annotate(frame, result)
    assert annotated[50, 70].any()
