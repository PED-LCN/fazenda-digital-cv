"""Score YOLOX against frame-aligned MOT boxes on a real recording."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from fazenda_cv.detection import YoloXOnnxDetector
from fazenda_cv.mot_boxes import read_mot_boxes
from fazenda_cv.mot_evaluation import score_mot_video
from fazenda_cv.tiled_detection import TiledDetector


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("video", type=Path)
    parser.add_argument("ground_truth", type=Path)
    parser.add_argument("model", type=Path)
    parser.add_argument("--first-frame", type=int, required=True)
    parser.add_argument("--last-frame", type=int, required=True)
    parser.add_argument("--coordinate-scale", type=float, required=True)
    parser.add_argument("--iou-threshold", type=float, default=0.5)
    parser.add_argument("--tile-size", type=int, default=0)
    parser.add_argument("--tile-overlap", type=int, default=0)
    parser.add_argument("--confidence-threshold", type=float, default=0.35)
    args = parser.parse_args()
    if (
        args.tile_size < 0
        or args.tile_overlap < 0
        or (args.tile_size == 0 and args.tile_overlap)
        or (args.tile_size and args.tile_overlap >= args.tile_size)
    ):
        parser.error("tile-size deve ser positivo e tile-overlap menor que tile-size")
    if not 0 < args.confidence_threshold <= 1:
        parser.error("confidence-threshold deve estar entre 0 (exclusivo) e 1")

    with args.ground_truth.open(encoding="utf-8") as source:
        labels = read_mot_boxes(
            source,
            coordinate_scale=args.coordinate_scale,
            first_frame=args.first_frame,
            last_frame=args.last_frame,
        )
    detector = YoloXOnnxDetector(str(args.model), confidence_threshold=args.confidence_threshold)
    if args.tile_size:
        detector = TiledDetector(detector, args.tile_size, args.tile_overlap)
    score = score_mot_video(
        args.video,
        detector,
        labels,
        first_frame=args.first_frame,
        last_frame=args.last_frame,
        iou_threshold=args.iou_threshold,
    )
    print(json.dumps({**asdict(score), "precision": score.precision, "recall": score.recall}))


if __name__ == "__main__":
    main()
