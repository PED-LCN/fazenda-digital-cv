"""Run a frozen plan against MOT video, caching raw model proposals for threshold sweeps."""

from __future__ import annotations

import argparse
import hashlib
import inspect
import json
import platform
import subprocess
import time
from dataclasses import asdict
from pathlib import Path

import cv2
import onnxruntime

from fazenda_cv.detection import YoloXOnnxDetector
from fazenda_cv.detection_benchmark import FrameObservation, combine_scores, score_sequence
from fazenda_cv.domain import Detection
from fazenda_cv.mot_boxes import read_mot_boxes
from fazenda_cv.tiled_detection import TiledDetector


def digest(path: Path) -> str:
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    plan = json.loads(args.plan.read_text())
    output = args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists():
        parser.error("Use um relatório novo; resultados anteriores são preservados")
    video = Path(plan["video"])
    labels_path = Path(plan["labels"])
    windows = plan["windows"]
    if any(first < 1 or last < first for first, last in windows):
        parser.error("Intervalo inválido")
    if any(b[0] <= a[1] for a, b in zip(windows, windows[1:], strict=False)):
        parser.error("Intervalos devem ser disjuntos e crescentes")
    with labels_path.open() as source:
        labels = read_mot_boxes(source, coordinate_scale=plan["coordinate_scale"])
    manifest = dict(
        plan=plan,
        plan_sha256=digest(args.plan),
        video_sha256=digest(video),
        labels_sha256=digest(labels_path),
        python=platform.python_version(),
        opencv=cv2.__version__,
        onnxruntime=onnxruntime.__version__,
        git_commit=subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        results=[],
    )
    manifest["runner_sha256"] = digest(Path(__file__))
    manifest["metrics_sha256"] = digest(Path(inspect.getfile(score_sequence)))
    for config in plan["configurations"]:
        model = Path(config["model"])
        identity = dict(
            model_sha256=digest(model),
            input_size=config["input_size"],
            tile_size=config["tile_size"],
            overlap=config["overlap"],
            video_sha256=manifest["video_sha256"],
            windows=windows,
            proposal_threshold=0.03,
            cpu_threads=4,
        )
        cache_key = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
        cache_path = output.parent / f"proposals-{cache_key}.json"
        if cache_path.exists():
            cached = json.loads(cache_path.read_text())
        else:
            base = YoloXOnnxDetector(
                str(model),
                input_size=config["input_size"],
                confidence_threshold=0.03,
                cpu_threads=4,
            )
            detector = TiledDetector(base, config["tile_size"], config["overlap"])
            cached = []
            for first, last in windows:
                capture = cv2.VideoCapture(str(video))
                if first > 1 and not capture.set(cv2.CAP_PROP_POS_FRAMES, first - 1):
                    raise OSError("Não foi possível posicionar vídeo")
                samples = []
                try:
                    for number in range(first, last + 1):
                        ok, image = capture.read()
                        if not ok:
                            raise OSError(f"Vídeo incompleto no quadro {number}")
                        started = time.monotonic()
                        boxes = detector.detect(image)
                        samples.append(
                            dict(
                                frame=number,
                                detections=[asdict(box) for box in boxes],
                                inference_seconds=time.monotonic() - started,
                            )
                        )
                        print(
                            json.dumps(dict(configuration=config["name"], frame=number)), flush=True
                        )
                finally:
                    capture.release()
                cached.append(samples)
            cache_path.write_text(json.dumps(cached))
        for threshold in config["thresholds"]:
            if not 0.03 <= threshold <= 1:
                raise ValueError("Limiar deve ser >= limiar de propostas 0,03")
            scores = []
            for samples in cached:
                observations = [
                    FrameObservation(
                        sample["frame"],
                        labels.get(sample["frame"], []),
                        [
                            Detection(**box)
                            for box in sample["detections"]
                            if box["confidence"] >= threshold
                        ],
                    )
                    for sample in samples
                ]
                scores.append(score_sequence(observations))
            result = dict(
                configuration=config,
                threshold=threshold,
                model_sha256=identity["model_sha256"],
                cache_sha256=digest(cache_path),
                aggregate=combine_scores(scores),
                windows=scores,
                inference_seconds=sum(
                    s["inference_seconds"] for samples in cached for s in samples
                ),
            )
            manifest["results"].append(result)
            print(
                json.dumps(dict(name=config["name"], threshold=threshold, **result["aggregate"])),
                flush=True,
            )
    output.write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    main()
