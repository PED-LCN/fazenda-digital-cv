"""Incremental all-frame evaluation with immutable inputs and SQLite restart points."""

from __future__ import annotations

import hashlib
import inspect
import json
import math
import sqlite3
import time
from dataclasses import asdict
from pathlib import Path

import cv2

from fazenda_cv.cattle_labels import read_cattle_frame
from fazenda_cv.detection import Detector
from fazenda_cv.detection_benchmark import FrameObservation, score_sequence


def file_hash(path: Path, algorithm: str = "sha256") -> str:
    with path.open("rb") as source:
        return hashlib.file_digest(source, algorithm).hexdigest()


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n")
    temporary.replace(path)


def summarize(db: sqlite3.Connection, fps: float) -> dict:
    states: dict[int, dict] = {}
    minutes: dict[int, dict] = {}
    total = dict(
        frames=0,
        true_positive=0,
        false_positive=0,
        false_negative=0,
        retained=0,
        retention_opportunities=0,
        inference_seconds=0.0,
        consecutive_hits=0,
        consecutive_opportunities=0,
    )
    for (raw,) in db.execute("SELECT payload FROM frames ORDER BY frame"):
        row = json.loads(raw)
        n = row["frame"]
        labels = row["labels"]
        hit_ids = set(row["matched_ids"])
        tp = len(hit_ids)
        fp = len(row["detections"]) - tp
        fn = len(labels) - tp
        minute = int(row.get("video_offset_ms", (n - 1) * 1000 / fps) / 60000)
        bucket = minutes.setdefault(
            minute,
            dict(
                minute=minute,
                frames=0,
                true_positive=0,
                false_positive=0,
                false_negative=0,
                retained=0,
                retention_opportunities=0,
                maximum_visible=0,
                visible_observations=0,
                moving_observations=0,
                reappearances=0,
                inference_seconds=0.0,
            ),
        )
        for item in (total, bucket):
            item["frames"] += 1
            item["true_positive"] += tp
            item["false_positive"] += fp
            item["false_negative"] += fn
            item["inference_seconds"] += row["inference_seconds"]
        bucket["maximum_visible"] = max(bucket["maximum_visible"], len(labels))
        bucket["visible_observations"] += len(labels)
        for label in labels:
            identity = label["object_id"]
            hit = identity in hit_ids
            state = states.setdefault(
                identity,
                dict(
                    object_id=identity,
                    visible=0,
                    matched=0,
                    first_match_frame=None,
                    retained=0,
                    opportunities=0,
                    last_frame=None,
                    last_hit=False,
                    last_center=None,
                    reappearances=0,
                    longest_miss_run=0,
                    miss_run=0,
                ),
            )
            x1, y1, x2, y2 = label["xyxy"]
            center = ((x1 + x2) / 2, (y1 + y2) / 2)
            if state["last_frame"] is not None:
                if n > state["last_frame"] + 1:
                    state["reappearances"] += 1
                    bucket["reappearances"] += 1
                    state["miss_run"] = 0
                else:
                    if math.dist(center, state["last_center"]) >= 2:
                        bucket["moving_observations"] += 1
                    if state["last_hit"]:
                        total["consecutive_opportunities"] += 1
                        total["consecutive_hits"] += hit
            if state["first_match_frame"] is not None:
                state["opportunities"] += 1
                state["retained"] += hit
                for item in (total, bucket):
                    item["retention_opportunities"] += 1
                    item["retained"] += hit
                state["miss_run"] = 0 if hit else state["miss_run"] + 1
                state["longest_miss_run"] = max(state["longest_miss_run"], state["miss_run"])
            elif hit:
                state["first_match_frame"] = n
            state["visible"] += 1
            state["matched"] += hit
            state["last_frame"] = n
            state["last_hit"] = hit
            state["last_center"] = center
    for item in [total, *minutes.values()]:
        tp, fp, fn = (item[k] for k in ("true_positive", "false_positive", "false_negative"))
        item["recall"] = tp / (tp + fn) if tp + fn else None
        item["precision"] = tp / (tp + fp) if tp + fp else None
        item["retention"] = (
            item["retained"] / item["retention_opportunities"]
            if item["retention_opportunities"]
            else None
        )
    tracks = []
    for state in states.values():
        tracks.append(
            {k: v for k, v in state.items() if not k.startswith("last_") and k != "miss_run"}
        )
        tracks[-1]["retention"] = (
            state["retained"] / state["opportunities"] if state["opportunities"] else None
        )
    total["consecutive_retention"] = (
        total["consecutive_hits"] / total["consecutive_opportunities"]
        if total["consecutive_opportunities"]
        else None
    )
    return dict(aggregate=total, minutes=list(minutes.values()), tracks=tracks)


def evaluate_video(
    video: Path,
    labels: Path,
    detector: Detector,
    database: Path,
    configuration: dict,
    *,
    minimum_seconds: float = 1800,
    stop_after: int | None = None,
) -> dict:
    database.parent.mkdir(parents=True, exist_ok=True)
    capture = cv2.VideoCapture(str(video))
    if not capture.isOpened():
        raise OSError("Vídeo indisponível")
    fps = capture.get(cv2.CAP_PROP_FPS)
    reported_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
    count = len(list(labels.glob("frame_*.txt")))
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    db = sqlite3.connect(database)
    try:
        if not math.isfinite(fps) or fps <= 0 or count / fps < minimum_seconds * 0.9:
            raise ValueError("Vídeo não atende à duração mínima requerida")
        # Missing annotation is an error, not an empty/negative frame.
        digest = hashlib.sha256()
        for index in range(count):
            path = labels / f"frame_{index:06d}.txt"
            digest.update(path.name.encode())
            digest.update(path.read_bytes())
        adapter_sources = []
        current = detector
        while current is not None:
            adapter_sources.append(file_hash(Path(inspect.getfile(type(current)))))
            current = getattr(current, "detector", None)
        specification = dict(
            video_sha256=file_hash(video),
            labels_sha256=digest.hexdigest(),
            detector=detector.model_version,
            configuration=configuration,
            fps=fps,
            expected_frames=count,
            header_reported_frames=reported_count,
            minimum_seconds=minimum_seconds,
            evaluator_sha256=file_hash(Path(__file__)),
            matching_sha256=file_hash(Path(inspect.getfile(score_sequence))),
            labels_parser_sha256=file_hash(Path(inspect.getfile(read_cattle_frame))),
            detector_code_sha256=adapter_sources,
        )
        encoded = json.dumps(specification, sort_keys=True)
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA synchronous=NORMAL")
        db.execute("CREATE TABLE IF NOT EXISTS metadata (id INTEGER PRIMARY KEY, spec TEXT)")
        db.execute("CREATE TABLE IF NOT EXISTS frames (frame INTEGER PRIMARY KEY,payload TEXT)")
        previous = db.execute("SELECT spec FROM metadata WHERE id=1").fetchone()
        if previous and previous[0] != encoded:
            raise ValueError("Checkpoint pertence a outros dados, código ou configuração")
        db.execute("INSERT OR IGNORE INTO metadata VALUES(1,?)", (encoded,))
        db.commit()
        done = db.execute("SELECT count(*) FROM frames").fetchone()[0]
        last = db.execute("SELECT coalesce(max(frame),0) FROM frames").fetchone()[0]
        if done != last:
            raise ValueError("Checkpoint não é um prefixo contínuo")
        eof_verified = db.execute("SELECT spec FROM metadata WHERE id=2").fetchone() is not None
        # Decode in sequence when resuming: header-based seeking can misalign VFR labels.
        if not (done == count and eof_verified):
            for _ in range(done):
                if not capture.grab():
                    raise OSError("Falha ao reconstituir posição do vídeo")
        last_row = db.execute("SELECT payload FROM frames ORDER BY frame DESC LIMIT 1").fetchone()
        previous_time = json.loads(last_row[0])["video_offset_ms"] if last_row else -1
        run_frames = 0
        for index in range(done, count):
            ok, image = capture.read()
            if not ok:
                raise OSError(f"Vídeo truncado no quadro {index + 1}")
            video_time = capture.get(cv2.CAP_PROP_POS_MSEC)
            if not math.isfinite(video_time) or video_time <= previous_time:
                raise ValueError("Timestamps do vídeo não são crescentes")
            previous_time = video_time
            expected = read_cattle_frame(
                labels / f"frame_{index:06d}.txt", index + 1, width, height
            )
            started = time.monotonic()
            detections = detector.detect(image)
            seconds = time.monotonic() - started
            score = score_sequence([FrameObservation(index + 1, expected, detections)])
            hit_ids = [track["object_id"] for track in score["tracks"] if track["matched"]]
            payload = dict(
                frame=index + 1,
                video_offset_ms=video_time,
                labels=[asdict(box) for box in expected],
                detections=[asdict(box) for box in detections],
                matched_ids=hit_ids,
                inference_seconds=seconds,
            )
            db.execute("INSERT INTO frames VALUES (?,?)", (index + 1, json.dumps(payload)))
            run_frames += 1
            if (index + 1) % 100 == 0:
                db.commit()
                write_json(
                    database.with_suffix(".progress.json"),
                    dict(
                        status="running",
                        frames=index + 1,
                        expected_frames=count,
                        analyzed_video_seconds=video_time / 1000,
                        configuration=configuration,
                    ),
                )
            if stop_after is not None and run_frames >= stop_after:
                break
        if db.execute("SELECT count(*) FROM frames").fetchone()[0] == count and not eof_verified:
            if capture.read()[0]:
                raise ValueError("Há quadros de vídeo adicionais sem rótulos correspondentes")
            db.execute("INSERT OR REPLACE INTO metadata VALUES(2, 'EOF verified')")
        db.commit()
        result = summarize(db, fps)
        actual = result["aggregate"]["frames"]
        first_payload = db.execute("SELECT payload FROM frames ORDER BY frame LIMIT 1").fetchone()
        last_payload = db.execute(
            "SELECT payload FROM frames ORDER BY frame DESC LIMIT 1"
        ).fetchone()
        start_ms = json.loads(first_payload[0])["video_offset_ms"] if first_payload else 0
        end_ms = json.loads(last_payload[0])["video_offset_ms"] if last_payload else 0
        period_ms = (end_ms - start_ms) / (actual - 1) if actual > 1 else 1000 / fps
        analyzed_seconds = (end_ms - start_ms + period_ms) / 1000 if actual else 0
        result.update(
            specification=specification,
            status="complete" if actual == count else "partial",
            analyzed_video_seconds=analyzed_seconds,
            expected_video_seconds=count / fps,
        )
        a = result["aggregate"]
        result["target_met"] = (
            actual == count
            and analyzed_seconds >= minimum_seconds - 0.001
            and a["recall"] is not None
            and a["recall"] >= 0.6
            and a["retention"] is not None
            and a["retention"] >= 0.7
        )
        result["global_targets_met"] = result["target_met"]
        acquired = [track for track in result["tracks"] if track["first_match_frame"] is not None]
        result["all_acquired_tracks_met"] = bool(acquired) and all(
            track["retention"] is not None and track["retention"] >= 0.7 for track in acquired
        )
        result["target_met"] = result["global_targets_met"] and result["all_acquired_tracks_met"]
        write_json(database.with_suffix(".summary.json"), result)
        return result
    except BaseException:
        db.rollback()
        raise
    finally:
        db.close()
        capture.release()
