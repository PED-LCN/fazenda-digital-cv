"""Download official long videos, extract safely, calibrate on video1, evaluate video3/4."""

from __future__ import annotations

import argparse
import fcntl
import json
import shutil
import tarfile
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path, PurePosixPath
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import cv2

from fazenda_cv.cattle_labels import read_cattle_frame
from fazenda_cv.detection import YoloXOnnxDetector
from fazenda_cv.detection_benchmark import FrameObservation, combine_scores, score_sequence
from fazenda_cv.long_evaluation import evaluate_video, file_hash, write_json
from fazenda_cv.tiled_detection import TiledDetector

EXPECTED_SIZE = 8263032538
EXPECTED_MD5 = "7aab872f1117aa46317b370b7f53b91d"
URL = "https://www.research-collection.ethz.ch/server/api/core/bitstreams/2dbbf79b-e731-4287-90cb-82fa4a86cc92/content"


class GrowingArchive:
    """Wait at EOF while the owned downloader appends; never manufacture input bytes."""

    def __init__(self, path: Path, download):
        self.path = path
        self.download = download
        self.position = 0

    def read(self, size: int) -> bytes:
        while True:
            available = self.path.stat().st_size if self.path.exists() else 0
            if available - self.position >= size or self.download.done():
                if self.download.done():
                    self.download.result()
                with self.path.open("rb") as source:
                    source.seek(self.position)
                    data = source.read(size)
                self.position += len(data)
                return data
            time.sleep(1)


def download_archive(archive: Path, output: Path) -> dict:
    archive.parent.mkdir(parents=True, exist_ok=True)
    if archive.exists() and archive.stat().st_size > EXPECTED_SIZE:
        raise ValueError("Arquivo local maior que o pacote oficial")
    while not archive.exists() or archive.stat().st_size < EXPECTED_SIZE:
        start = archive.stat().st_size if archive.exists() else 0
        end = min(start + 16 * 1024 * 1024 - 1, EXPECTED_SIZE - 1)
        for attempt in range(12):
            try:
                # Recalculate start after an interrupted response: written bytes are preserved.
                start = archive.stat().st_size if archive.exists() else 0
                if start > end:
                    break
                request = Request(
                    URL,
                    headers={
                        "User-Agent": "FazendaDigitalCV academic research",
                        "Accept-Encoding": "identity",
                        "Range": f"bytes={start}-{end}",
                    },
                )
                with urlopen(request, timeout=60) as response:
                    expected = f"bytes {start}-{end}/{EXPECTED_SIZE}"
                    if response.status != 206 or response.headers.get("Content-Range") != expected:
                        raise ValueError(
                            "Servidor não confirmou o intervalo exato; nada foi anexado"
                        )
                    remaining = end - start + 1
                    with archive.open("ab", buffering=0) as target:
                        while remaining:
                            chunk = response.read(min(1024 * 1024, remaining))
                            if not chunk:
                                raise OSError("Resposta terminou antes do intervalo pedido")
                            target.write(chunk)
                            remaining -= len(chunk)
                            write_json(
                                output / "download.json",
                                dict(
                                    status="downloading",
                                    downloaded_bytes=archive.stat().st_size,
                                    expected_bytes=EXPECTED_SIZE,
                                    source_url=URL,
                                    expected_md5=EXPECTED_MD5,
                                ),
                            )
                break
            except (OSError, HTTPError) as error:
                with (output / "download.log").open("a") as log:
                    log.write(f"{type(error).__name__}: {error}\n")
                if attempt == 11:
                    raise
                retry = (
                    error.headers.get("Retry-After", "30") if isinstance(error, HTTPError) else "30"
                )
                time.sleep(min(300, int(retry)) if retry.isdigit() else 30)
    actual = file_hash(archive, "md5")
    if actual != EXPECTED_MD5:
        raise ValueError("MD5 do acervo não confere")
    evidence = dict(
        status="verified",
        bytes=EXPECTED_SIZE,
        md5=actual,
        sha256=file_hash(archive),
        source_url=URL,
    )
    write_json(output / "download.json", evidence)
    return evidence


def calibrate(root: Path, models: Path, output: Path) -> dict:
    checkpoint = output / "frozen_configuration.json"
    if checkpoint.exists():
        return json.loads(checkpoint.read_text())
    video = root / "tracking_new/video1/video1.mp4"
    labels = video.parent / "labels"
    capture = cv2.VideoCapture(str(video))
    if not capture.isOpened():
        raise OSError("Vídeo de desenvolvimento indisponível")
    count = len(list(labels.glob("frame_*.txt")))
    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    starts = (0, count // 2, max(0, count - 5))
    samples = [[] for _ in starts]
    try:
        for index in range(count):
            if not capture.grab():
                raise OSError(f"Vídeo de desenvolvimento truncado no quadro {index + 1}")
            for group, first in enumerate(starts):
                if first <= index < first + 5:
                    ok, image = capture.retrieve()
                    if not ok:
                        raise OSError("Quadro de desenvolvimento não decodificável")
                    expected = read_cattle_frame(
                        labels / f"frame_{index:06d}.txt", index + 1, width, height
                    )
                    samples[group].append((index + 1, image, expected))
        if capture.read()[0]:
            raise ValueError("Há quadros de desenvolvimento sem rótulos")
    finally:
        capture.release()
    results = []
    for name, size, tile in [("tiny", 416, 0), ("s", 640, 0), ("s", 640, 1280), ("s", 640, 960)]:
        model = models / f"yolox_{name}.onnx"
        detector = YoloXOnnxDetector(
            str(model), input_size=size, confidence_threshold=0.03, cpu_threads=4
        )
        if tile:
            detector = TiledDetector(detector, tile, 128)
        proposals = [
            [(number, gt, detector.detect(image)) for number, image, gt in window]
            for window in samples
        ]
        for threshold in (0.35, 0.2, 0.1, 0.05):
            scores = [
                score_sequence(
                    [
                        FrameObservation(n, gt, [b for b in boxes if b.confidence >= threshold])
                        for n, gt, boxes in window
                    ]
                )
                for window in proposals
            ]
            config = dict(
                model=str(model),
                input_size=size,
                confidence_threshold=threshold,
                model_sha256=file_hash(model),
                cpu_threads=4,
                tile_size=tile,
                overlap=128 if tile else 0,
            )
            results.append(dict(configuration=config, score=combine_scores(scores), windows=scores))
    eligible = [
        r for r in results if r["score"]["target_met"] and (r["score"]["precision"] or 0) >= 0.6
    ]
    selected = max(
        eligible or results,
        key=lambda r: (
            (r["score"]["precision"] or 0)
            if eligible
            else (r["score"]["recall"] or 0) + (r["score"]["retention"] or 0)
        ),
    )
    write_json(
        output / "development_video1.json",
        dict(
            results=results,
            selected=selected,
            video_sha256=file_hash(video),
            windows=[[w[0][0], w[-1][0]] for w in samples],
        ),
    )
    write_json(checkpoint, selected["configuration"])
    return selected["configuration"]


def evaluate_selected(root: Path, models: Path, output: Path, identity: str) -> dict:
    configuration = calibrate(root, models, output)
    if file_hash(Path(configuration["model"])) != configuration["model_sha256"]:
        raise ValueError("Pesos diferem da configuração congelada")
    detector = YoloXOnnxDetector(
        configuration["model"],
        input_size=configuration["input_size"],
        confidence_threshold=configuration["confidence_threshold"],
        cpu_threads=4,
    )
    if configuration["tile_size"]:
        detector = TiledDetector(detector, configuration["tile_size"], configuration["overlap"])
    video = root / f"tracking_new/{identity}/{identity}.mp4"
    result = evaluate_video(
        video, video.parent / "labels", detector, output / f"{identity}.sqlite3", configuration
    )
    # Keep unmodified frames for review: original timestamps across the entire sequence.
    capture = cv2.VideoCapture(str(video))
    fps = capture.get(cv2.CAP_PROP_FPS)
    reviews = output / f"{identity}_scene_review"
    reviews.mkdir(exist_ok=True)
    try:
        for second in [0, 300, 600, 900, 1200, 1500, 1799]:
            if capture.set(cv2.CAP_PROP_POS_FRAMES, round(second * fps)):
                ok, image = capture.read()
                if ok:
                    cv2.imwrite(str(reviews / f"{second:04d}s.jpg"), image)
    finally:
        capture.release()
    return result


def run(archive: Path, root: Path, models: Path, output: Path) -> None:
    output.mkdir(parents=True, exist_ok=True)
    write_json(
        output / "job.json",
        dict(
            status="running",
            required_video_seconds=1800,
            videos=["video3", "video4"],
            all_frames=True,
            download_expected_bytes=EXPECTED_SIZE,
            development_video="video1",
            scene_review_required=True,
        ),
    )
    futures = {}
    with ThreadPoolExecutor(max_workers=2) as pool:
        download = pool.submit(download_archive, archive, output)
        stream = GrowingArchive(archive, download)
        try:
            with tarfile.open(fileobj=stream, mode="r|gz") as tar:
                for member in tar:
                    parts = PurePosixPath(member.name).parts
                    if (
                        not member.isfile()
                        or len(parts) < 3
                        or parts[0] != "tracking_new"
                        or parts[1] not in {"video1", "video3", "video4"}
                        or ".." in parts
                    ):
                        continue
                    relative = Path(*parts)
                    destination = root / relative
                    if destination.suffix.lower() not in {".txt", ".mp4"}:
                        continue
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    if not destination.exists() or destination.stat().st_size != member.size:
                        source = tar.extractfile(member)
                        if source is None:
                            raise OSError("Membro de arquivo indisponível")
                        temporary = destination.with_suffix(destination.suffix + ".part")
                        with source, temporary.open("wb") as target:
                            shutil.copyfileobj(source, target, length=1024 * 1024)
                        if temporary.stat().st_size != member.size:
                            raise OSError("Extração incompleta")
                        temporary.replace(destination)
                    if destination.suffix.lower() == ".mp4":
                        identity = parts[1]
                        write_json(
                            output / f"{identity}_source.json",
                            dict(
                                path=str(destination),
                                sha256=file_hash(destination),
                                bytes=member.size,
                                archive_verified=download.done(),
                            ),
                        )
                        if identity == "video1":
                            calibrate(root, models, output)
                        else:
                            futures[identity] = pool.submit(
                                evaluate_selected, root, models, output, identity
                            )
                        if identity == "video4":
                            break
            integrity = download.result()
            results = {name: future.result() for name, future in futures.items()}
            if set(results) != {"video3", "video4"}:
                raise ValueError("Pacote não contém os dois testes")
            write_json(
                output / "job.json",
                dict(
                    status="completed_requires_scene_review",
                    archive=integrity,
                    videos={
                        name: dict(
                            status=r["status"],
                            target_met=r["target_met"],
                            analyzed_video_seconds=r["analyzed_video_seconds"],
                            aggregate=r["aggregate"],
                        )
                        for name, r in results.items()
                    },
                    scene_review_required=True,
                ),
            )
        except BaseException as error:
            write_json(
                output / "job.json",
                dict(
                    status="interrupted",
                    error_type=type(error).__name__,
                    message=str(error),
                    resume="Execute novamente o mesmo comando; checkpoints serão preservados",
                ),
            )
            raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, required=True)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--models", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    with (args.output / "job.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as error:
            raise RuntimeError("Já existe uma avaliação em execução nesta pasta") from error
        run(
            args.archive.resolve(),
            args.data.resolve(),
            args.models.resolve(),
            args.output.resolve(),
        )


if __name__ == "__main__":
    main()
