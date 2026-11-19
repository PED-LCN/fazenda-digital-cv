"""Compare cattle detectors on ETH development footage and evaluate a frozen profile."""

from __future__ import annotations

import argparse
import csv
import fcntl
import hashlib
import importlib.metadata
import json
import multiprocessing
import platform
import re
import resource
import subprocess
import sys
import time
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from tempfile import TemporaryDirectory

import cv2
import numpy as np
from run_long_cattle_job import EXPECTED_MD5, EXPECTED_SIZE

from fazenda_cv.alternate_detection import RTDetrCattleDetector, YoloV8CattleDetector
from fazenda_cv.cattle_labels import read_cattle_frame
from fazenda_cv.detection import YoloXOnnxDetector
from fazenda_cv.detection_benchmark import FrameObservation, combine_scores, score_sequence
from fazenda_cv.long_evaluation import evaluate_video, file_hash, write_json
from fazenda_cv.tiled_detection import TiledDetector

WINDOW_SIZE = 30
RUNTIME_PACKAGES = (
    "numpy",
    "opencv-python-headless",
    "opencv-python",
    "onnxruntime",
    "torch",
    "torchvision",
    "transformers",
    "ultralytics",
)


def environment() -> dict:
    packages = {}
    for name in RUNTIME_PACKAGES:
        try:
            packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            pass
    root = Path(__file__).resolve().parents[1]
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, check=True, capture_output=True, text=True
    ).stdout.strip()
    pipeline_files = (
        "alternate_detection.py",
        "cattle_labels.py",
        "detection.py",
        "detection_benchmark.py",
        "domain.py",
        "long_evaluation.py",
        "model_qualification.py",
        "mot_boxes.py",
        "tiled_detection.py",
    )
    source_hashes = {
        str(path.relative_to(root)): file_hash(path)
        for path in [
            Path(__file__).resolve(),
            *(root / "src/fazenda_cv" / n for n in pipeline_files),
        ]
    }
    return {
        "git_commit": commit,
        "source_sha256": source_hashes,
        "packages": packages,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "processor": platform.processor(),
    }


def profile_assets(profile: dict) -> dict:
    path = Path(profile["path"])
    backend = profile["backend"]
    if backend == "rtdetr":
        files = [
            path / name for name in ("model.safetensors", "config.json", "preprocessor_config.json")
        ]
    elif backend in {"yolox", "yolov8"}:
        files = [path]
    else:
        raise ValueError(f"Backend desconhecido: {backend}")
    if any(not profile.get(field) for field in ("source_url", "license")):
        raise FileNotFoundError("Procedência ou condições de uso dos pesos não registradas")
    if backend == "yolov8" and not profile.get("expected_sha256"):
        raise FileNotFoundError("YOLOv8 requer SHA-256 conferido após obtenção da fonte")
    hashes = {p.name: file_hash(p) for p in files}
    if profile.get("expected_sha256") and hashes[files[0].name] != profile["expected_sha256"]:
        raise ValueError(f"SHA-256 dos pesos não confere: {path}")
    return hashes


def detector_for(profile: dict, hashes: dict):
    path = Path(profile["path"])
    size, confidence, threads = (
        profile["input_size"],
        profile["confidence"],
        profile["cpu_threads"],
    )
    match profile["backend"]:
        case "yolox":
            detector = YoloXOnnxDetector(
                str(path), input_size=size, confidence_threshold=confidence, cpu_threads=threads
            )
        case "yolov8":
            detector = YoloV8CattleDetector(path, hashes[path.name], size, confidence, threads)
        case "rtdetr":
            detector = RTDetrCattleDetector(path, hashes["model.safetensors"], confidence, threads)
        case _:
            raise ValueError("Detector desconhecido")
    if profile["tile_size"]:
        detector = TiledDetector(detector, profile["tile_size"], profile["overlap"])
    return detector


def video_paths(data: Path, identity: str) -> tuple[Path, Path]:
    directory = data / "tracking_new" / identity
    return directory / f"{identity}.mp4", directory / "labels"


def window_starts(count: int) -> tuple[int, int, int]:
    if count < 3 * WINDOW_SIZE:
        raise ValueError("Vídeo precisa comportar três janelas de 30 quadros")
    return 0, (count - WINDOW_SIZE) // 2, count - WINDOW_SIZE


def labels_hash(labels: Path) -> tuple[int, str]:
    count = len(list(labels.glob("frame_*.txt")))
    digest = hashlib.sha256()
    for index in range(count):
        path = labels / f"frame_{index:06d}.txt"
        digest.update(path.name.encode())
        digest.update(path.read_bytes())
    return count, digest.hexdigest()


def review_image(path: Path, image, observation: FrameObservation) -> None:
    def rectangle(box, color):
        x1, y1, x2, y2 = map(round, box)
        cv2.rectangle(image, (x1, y1), (x2, y2), color, 3)

    for expected in observation.labels:
        rectangle(expected.xyxy, (0, 255, 255))
    for actual in observation.detections:
        rectangle((actual.x1, actual.y1, actual.x2, actual.y2), (0, 255, 0))
    if not cv2.imwrite(str(path), image):
        raise OSError(f"Falha ao gravar imagem de revisão: {path}")


def sample_video(video: Path, labels: Path, count: int, directory: Path) -> list[list]:
    capture = cv2.VideoCapture(str(video))
    starts = window_starts(count)
    windows = [[] for _ in starts]
    groups = {
        i: group for group, start in enumerate(starts) for i in range(start, start + WINDOW_SIZE)
    }
    try:
        if not capture.isOpened():
            raise OSError(f"Vídeo indisponível: {video}")
        for index in range(count):
            if not capture.grab():
                raise OSError(f"Vídeo truncado no quadro {index + 1}")
            if index not in groups:
                continue
            ok, image = capture.retrieve()
            if not ok:
                raise OSError(f"Quadro {index + 1} não decodificável")
            h, w = image.shape[:2]
            expected = read_cattle_frame(labels / f"frame_{index:06d}.txt", index + 1, w, h)
            path = directory / f"{index + 1:06d}.npy"
            np.save(path, image, allow_pickle=False)
            windows[groups[index]].append((index + 1, path, expected))
        if capture.grab():
            raise ValueError("Há quadros sem rótulos")
    finally:
        capture.release()
    return windows


def run_profile(windows: list[list], profile: dict, hashes: dict, out: Path) -> dict:
    cv2.setNumThreads(profile["cpu_threads"])
    detector = detector_for(profile, hashes)
    detector.detect(np.load(windows[0][0][1], allow_pickle=False))
    latency = []
    scores = []
    for window in windows:
        observations = []
        for index, (frame, path, expected) in enumerate(window):
            image = np.load(path, allow_pickle=False)
            started = time.perf_counter()
            detections = detector.detect(image)
            latency.append((time.perf_counter() - started) * 1000)
            observation = FrameObservation(frame, expected, detections)
            observations.append(observation)
            if index == 0:
                review_image(out / f"{profile['id']}-{frame:06d}.jpg", image, observation)
        scores.append(score_sequence(observations))
    p50, p95 = map(float, np.percentile(latency, [50, 95]))
    return {
        "configuration": profile,
        "asset_sha256": hashes,
        "status": "completed",
        "windows": scores,
        "tracks": track_totals(scores),
        "score": combine_scores(scores),
        "p50_ms": p50,
        "p95_ms": p95,
        "peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        * (1 if sys.platform == "darwin" else 1024),
    }


def track_totals(windows: list[dict]) -> list[dict]:
    totals = defaultdict(lambda: dict(visible=0, matched=0, retained=0, opportunities=0))
    for window in windows:
        for track in window["tracks"]:
            total = totals[track["object_id"]]
            for key in total:
                total[key] += track[key]
    return [
        {
            "object_id": identity,
            **total,
            "retention": total["retained"] / total["opportunities"]
            if total["opportunities"]
            else None,
        }
        for identity, total in sorted(totals.items())
    ]


def choose(results: list[dict]) -> dict | None:
    eligible = []
    for result in results:
        if result["status"] != "completed":
            continue
        score = result["score"]
        tracks = [
            track["retention"] for track in result["tracks"] if track["retention"] is not None
        ]
        if (
            score["target_met"]
            and (score["precision"] or 0) >= 0.6
            and tracks
            and min(tracks) >= 0.7
        ):
            eligible.append(result)
    return min(
        eligible,
        default=None,
        key=lambda item: (-item["score"]["precision"], item["p95_ms"], item["configuration"]["id"]),
    )


def compare(data: Path, config: Path, out: Path) -> None:
    profiles = json.loads(config.read_text())["profiles"]
    ids = [p["id"] for p in profiles]
    if len(ids) != len(set(ids)) or any(not re.fullmatch(r"[a-z0-9_-]+", i) for i in ids):
        raise ValueError("Identificadores de perfil inválidos ou duplicados")
    video, labels = video_paths(data, "video1")
    count, label_digest = labels_hash(labels)
    starts = window_starts(count)
    report = {
        "environment": environment(),
        "video": str(video),
        "video_sha256": file_hash(video),
        "labels_sha256": label_digest,
        "config_sha256": file_hash(config),
        "windows": [[i + 1, i + WINDOW_SIZE] for i in starts],
        "results": [],
    }
    out.mkdir(parents=True, exist_ok=False)
    results = report["results"]
    with TemporaryDirectory(prefix="frames-", dir=out) as directory:
        samples = sample_video(video, labels, count, Path(directory))
        for profile in profiles:
            profile["path"] = str((config.parent / profile["path"]).resolve())
            print(f"Perfil {profile['id']}", flush=True)
            try:
                hashes = profile_assets(profile)
                with ProcessPoolExecutor(
                    max_workers=1, mp_context=multiprocessing.get_context("spawn")
                ) as pool:
                    result = pool.submit(run_profile, samples, profile, hashes, out).result()
            except (FileNotFoundError, ImportError) as error:
                result = {"configuration": profile, "status": "unavailable", "reason": str(error)}
            results.append(result)
            write_json(out / "comparison.json", report)
    required_complete = all(
        r["status"] == "completed" or r["configuration"].get("optional") for r in results
    )
    selected = choose(results) if required_complete else None
    report["selected"] = selected["configuration"]["id"] if selected else None
    report["decision"] = (
        "frozen" if selected else "needs_fine_tuning" if required_complete else "incomplete"
    )
    write_json(out / "comparison.json", report)
    if selected:
        write_json(
            out / "frozen.json",
            {key: selected[key] for key in ("configuration", "asset_sha256")}
            | {
                "environment": report["environment"],
                "comparison_sha256": file_hash(out / "comparison.json"),
            },
        )
    fields = [
        "profile",
        "status",
        "true_positive",
        "false_positive",
        "false_negative",
        "precision",
        "recall",
        "retention",
        "p50_ms",
        "p95_ms",
        "peak_rss_bytes",
    ]
    with (out / "comparison.csv").open("x", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for result in results:
            writer.writerow(
                result | result.get("score", {}) | {"profile": result["configuration"]["id"]}
            )


def evaluate_frozen(data: Path, frozen: Path, archive: Path, out: Path) -> None:
    manifest = json.loads(frozen.read_text())
    report = frozen.with_name("comparison.json")
    if file_hash(report) != manifest["comparison_sha256"]:
        raise ValueError("Relatório de desenvolvimento difere do manifesto congelado")
    comparison = json.loads(report.read_text())
    profile = manifest["configuration"]
    selected = choose(comparison["results"])
    if (
        comparison["decision"] != "frozen"
        or selected is None
        or profile != selected["configuration"]
        or manifest["asset_sha256"] != selected["asset_sha256"]
        or manifest["environment"] != comparison["environment"]
    ):
        raise ValueError("Manifesto difere do perfil selecionado em desenvolvimento")
    hashes = profile_assets(profile)
    if hashes != manifest["asset_sha256"]:
        raise ValueError("Arquivos do detector diferem do manifesto congelado")
    runtime = environment()
    if any(
        runtime[key] != manifest["environment"][key]
        for key in ("source_sha256", "packages", "python")
    ):
        raise ValueError("Código ou versões do ambiente diferem do manifesto congelado")
    if archive.stat().st_size != EXPECTED_SIZE or file_hash(archive, "md5") != EXPECTED_MD5:
        raise ValueError("Arquivo ETH não corresponde ao checksum oficial")
    detector = detector_for(profile, hashes)
    out.mkdir(parents=True, exist_ok=True)
    configuration = profile | {"frozen_sha256": file_hash(frozen), "runtime": runtime}
    results = {}
    for identity in ("video3", "video4"):
        print(f"Avaliação reservada {identity}", flush=True)
        video, labels = video_paths(data, identity)
        results[identity] = evaluate_video(
            video, labels, detector, out / f"{identity}.sqlite3", configuration
        )
        write_json(
            out / "reserved.json",
            {
                "archive_md5": EXPECTED_MD5,
                "videos": results,
                "targets_met": len(results) == 2
                and all(result["target_met"] for result in results.values()),
            },
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--config", type=Path)
    mode.add_argument("--frozen", type=Path)
    parser.add_argument("--archive", type=Path)
    args = parser.parse_args()
    if args.frozen:
        if not args.archive:
            parser.error("--frozen requer --archive")
        args.output.mkdir(parents=True, exist_ok=True)
        with (args.output / "job.lock").open("a") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as error:
                raise RuntimeError("Já existe uma avaliação nesta pasta") from error
            evaluate_frozen(args.data, args.frozen, args.archive, args.output)
    else:
        compare(args.data, args.config, args.output)


if __name__ == "__main__":
    main()
