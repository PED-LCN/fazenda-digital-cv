import json

import pytest

from fazenda_cv.__main__ import main
from fazenda_cv.run_report import RunReport


def test_report_records_detection_coverage_and_passages(tmp_path):
    report = RunReport("curral-1", "yolox-onnx:sha256:abc")
    report.record_frame(0, 0)
    report.record_frame(2, 1)
    report.record_frame(1, 0)
    path = tmp_path / "report.json"

    report.save(path, 1.5)

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["frames"] == 3
    assert payload["frames_with_cattle"] == 2
    assert payload["detections"] == 3
    assert payload["max_cattle_in_frame"] == 2
    assert payload["passage_events"] == 1
    assert payload["processing_fps"] == 2.0
    assert payload["validation_level"] == "operational_smoke_test"


def test_report_rejects_invalid_measurements(tmp_path):
    report = RunReport("curral-1", "model")
    with pytest.raises(ValueError):
        report.record_frame(-1, 0)
    with pytest.raises(ValueError):
        report.save(tmp_path / "report.json", 0)


def test_cli_rejects_model_card_with_wrong_hash(tmp_path):
    (tmp_path / "weights.onnx").write_bytes(b"weights")
    (tmp_path / "model.toml").write_text(
        'path = "weights.onnx"\n'
        'source_url = "https://example.org/weights.onnx"\n'
        'license = "Apache-2.0"\n'
        f'sha256 = "{"0" * 64}"\n'
        "input_size = 416\n"
        "cattle_class_id = 0\n"
        'class_names = ["cow"]\n',
        encoding="utf-8",
    )
    with pytest.raises(SystemExit, match="2"):
        main(
            ["--source", str(tmp_path / "unused.avi"), "--model-card", str(tmp_path / "model.toml")]
        )
