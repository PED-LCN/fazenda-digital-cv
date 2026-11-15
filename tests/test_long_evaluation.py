import json
from pathlib import Path

import cv2
import numpy as np
import pytest

from fazenda_cv.cattle_labels import read_cattle_frame
from fazenda_cv.domain import Detection
from fazenda_cv.long_evaluation import evaluate_video


class FixedDetector:
    model_version = "unit-test"

    def detect(self, frame):
        return [Detection(16, 12, 48, 36, 0.9, 19)]


def fixture_video(tmp_path: Path):
    video = tmp_path / "video.avi"
    labels = tmp_path / "labels"
    labels.mkdir()
    writer = cv2.VideoWriter(str(video), cv2.VideoWriter_fourcc(*"MJPG"), 5, (64, 48))
    assert writer.isOpened()
    for i in range(10):
        writer.write(np.zeros((48, 64, 3), dtype=np.uint8))
        (labels / f"frame_{i:06d}.txt").write_text("3 0.5 0.5 0.5 0.5\n")
    writer.release()
    return video, labels


def test_resume_equals_uninterrupted_metrics_and_does_not_duplicate(tmp_path):
    video, labels = fixture_video(tmp_path)
    database = tmp_path / "resume.db"
    partial = evaluate_video(
        video, labels, FixedDetector(), database, {}, minimum_seconds=2, stop_after=4
    )
    assert partial["status"] == "partial"
    assert not partial["target_met"]
    assert partial["aggregate"]["frames"] == 4
    resumed = evaluate_video(video, labels, FixedDetector(), database, {}, minimum_seconds=2)
    direct = evaluate_video(
        video, labels, FixedDetector(), tmp_path / "direct.db", {}, minimum_seconds=2
    )
    assert resumed["status"] == "complete"
    for key in [
        "frames",
        "true_positive",
        "false_positive",
        "false_negative",
        "retained",
        "retention_opportunities",
        "recall",
        "precision",
        "retention",
    ]:
        assert resumed["aggregate"][key] == direct["aggregate"][key]
    assert resumed["aggregate"]["frames"] == 10
    assert resumed["tracks"][0]["retention"] == 1
    assert resumed["target_met"]
    repeated = evaluate_video(video, labels, FixedDetector(), database, {}, minimum_seconds=2)
    assert repeated["aggregate"]["frames"] == 10
    with pytest.raises(ValueError, match="outros dados"):
        evaluate_video(
            video, labels, FixedDetector(), database, {"confidence": 0.1}, minimum_seconds=2
        )


def test_short_source_and_missing_labels_fail(tmp_path):
    video, labels = fixture_video(tmp_path)
    with pytest.raises(ValueError, match="duração"):
        evaluate_video(video, labels, FixedDetector(), tmp_path / "short.db", {})
    (labels / "frame_000004.txt").unlink()
    with pytest.raises(FileNotFoundError):
        evaluate_video(
            video, labels, FixedDetector(), tmp_path / "missing.db", {}, minimum_seconds=2
        )


def test_normalized_labels_keep_individual_id_and_reject_duplicate(tmp_path):
    path = tmp_path / "frame_000000.txt"
    path.write_text("8 .5 .5 .5 .5\n")
    box = read_cattle_frame(path, 1, 100, 80)[0]
    assert box.object_id == 8
    assert box.xyxy == (25, 20, 75, 60)
    path.write_text("8 .5 .5 .5 .5\n8 .5 .5 .5 .5\n")
    with pytest.raises(ValueError):
        read_cattle_frame(path, 1, 100, 80)


def test_retention_state_survives_minute_boundary(tmp_path):
    import sqlite3
    from dataclasses import asdict

    from fazenda_cv.long_evaluation import summarize

    db = sqlite3.connect(":memory:")
    db.execute("CREATE TABLE frames(frame INTEGER PRIMARY KEY,payload TEXT)")
    for frame, hit in [(1, True), (2, True), (3, False)]:
        payload = dict(
            frame=frame,
            labels=[dict(object_id=3, xyxy=[0, 0, 10, 10])],
            matched_ids=[3] if hit else [],
            detections=[asdict(FixedDetector().detect(None)[0])] if hit else [],
            inference_seconds=0.1,
        )
        db.execute("INSERT INTO frames VALUES(?,?)", (frame, json.dumps(payload)))
    result = summarize(db, 1 / 30)
    db.close()
    # Frames 1/2 belong to minute 0; frame 3 to minute 1.
    assert result["aggregate"]["retention"] == 0.5
    assert result["minutes"][1]["retention"] == 0
    assert result["tracks"][0]["longest_miss_run"] == 1


def test_header_frame_overestimate_does_not_invent_missing_video_frames(tmp_path, monkeypatch):
    video, labels = fixture_video(tmp_path)
    original = cv2.VideoCapture

    class HeaderOverestimate:
        def __init__(self, path):
            self.capture = original(path)

        def get(self, key):
            if key == cv2.CAP_PROP_FRAME_COUNT:
                return 27
            return self.capture.get(key)

        def __getattr__(self, key):
            return getattr(self.capture, key)

    monkeypatch.setattr(cv2, "VideoCapture", HeaderOverestimate)
    result = evaluate_video(
        video, labels, FixedDetector(), tmp_path / "header.db", {}, minimum_seconds=2
    )
    assert result["status"] == "complete"
    assert result["specification"]["header_reported_frames"] == 27
    assert result["aggregate"]["frames"] == 10
    assert result["analyzed_video_seconds"] == pytest.approx(2)


def test_growing_archive_stream_can_read_complete_tar(tmp_path):
    import importlib.util
    import io
    import tarfile
    from concurrent.futures import Future

    path_script = Path(__file__).resolve().parents[1] / "scripts/run_long_cattle_job.py"
    spec = importlib.util.spec_from_file_location("long_job", path_script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    GrowingArchive = module.GrowingArchive

    path = tmp_path / "archive.tar.gz"
    with tarfile.open(path, "w:gz") as archive:
        member = tarfile.TarInfo("tracking_new/video1/labels/frame_000000.txt")
        data = b"1 .5 .5 .2 .2\n"
        member.size = len(data)
        archive.addfile(member, io.BytesIO(data))
    download = Future()
    download.set_result({"status": "verified"})
    stream = GrowingArchive(path, download)
    with tarfile.open(fileobj=stream, mode="r|gz") as archive:
        member = next(iter(archive))
        assert archive.extractfile(member).read() == data


def test_ranged_download_resumes_and_checks_official_digest(tmp_path, monkeypatch):
    import hashlib
    import importlib.util
    import io

    path_script = Path(__file__).resolve().parents[1] / "scripts/run_long_cattle_job.py"
    spec = importlib.util.spec_from_file_location("range_job", path_script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    data = b"official archive bytes for test"
    archive = tmp_path / "archive.gz"
    archive.write_bytes(data[:8])
    monkeypatch.setattr(module, "EXPECTED_SIZE", len(data))
    monkeypatch.setattr(module, "EXPECTED_MD5", hashlib.md5(data).hexdigest())
    calls = []

    class Response(io.BytesIO):
        status = 206
        headers = {"Content-Range": f"bytes 8-{len(data) - 1}/{len(data)}"}

    def fetch(request, timeout):
        calls.append(request.get_header("Range"))
        return Response(data[8:])

    monkeypatch.setattr(module, "urlopen", fetch)
    result = module.download_archive(archive, tmp_path)
    assert archive.read_bytes() == data
    assert calls == [f"bytes=8-{len(data) - 1}"]
    assert result["status"] == "verified"
