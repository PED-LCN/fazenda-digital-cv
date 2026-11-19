from pathlib import Path

import pytest


@pytest.fixture
def runner(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1] / "scripts"))
    import compare_cattle_detectors

    return compare_cattle_detectors


def candidate(name, precision, p95, retention):
    return {
        "configuration": {"id": name},
        "status": "completed",
        "score": {"target_met": True, "precision": precision},
        "tracks": [{"retention": retention}],
        "p95_ms": p95,
    }


def test_selection_requires_all_metrics_then_breaks_ties(runner):
    slow = candidate("slow", 0.82, 90, 0.77)
    winner = candidate("a", 0.82, 40, 0.71)
    same = candidate("b", 0.82, 40, 0.91)
    low_precision = candidate("low-precision", 0.59, 44, 0.95)
    low_retention = candidate("low-retention", 0.98, 40, 0.69)
    undefined = candidate("undefined", 0.99, 10, None)
    assert runner.choose([slow, same, low_precision, winner, low_retention, undefined]) == winner
    assert runner.choose([low_retention, undefined, low_precision]) is None


def test_coverage_rejects_missing_label_and_windows_match(runner, tmp_path):
    (tmp_path / "frame_000000.txt").touch()
    (tmp_path / "frame_000002.txt").touch()
    with pytest.raises(FileNotFoundError, match="frame_000001"):
        runner.labels_hash(tmp_path)
    assert runner.window_starts(4501) == (0, 2235, 4471)


def test_evaluation_rejects_edited_frozen_profile(runner, tmp_path):
    entry = candidate("profile", 0.92, 30, 0.75)
    entry["asset_sha256"] = {"model.pt": "sha"}
    report = tmp_path / "comparison.json"
    runner.write_json(report, {"results": [entry], "environment": {}, "decision": "frozen"})
    manifest = tmp_path / "frozen.json"
    runner.write_json(
        manifest,
        {
            "configuration": {"id": "other"},
            "asset_sha256": entry["asset_sha256"],
            "environment": {},
            "comparison_sha256": runner.file_hash(report),
        },
    )
    with pytest.raises(ValueError, match="perfil selecionado"):
        runner.evaluate_frozen(tmp_path, manifest, tmp_path / "archive", tmp_path / "out")
