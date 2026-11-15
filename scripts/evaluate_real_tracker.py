"""Score the built-in tracker with YOLOX on frame-aligned real MOT video."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from fazenda_cv.detection import YoloXOnnxDetector
from fazenda_cv.mot_data import read_mot_positions
from fazenda_cv.mot_tracking import score_mot_tracking_video
from fazenda_cv.tiled_detection import TiledDetector
from fazenda_cv.tracking import CentroidTracker


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("video", type=Path)
    parser.add_argument("ground_truth", type=Path)
    parser.add_argument("model", type=Path)
    parser.add_argument("--first-frame", type=int, required=True)
    parser.add_argument("--last-frame", type=int, required=True)
    parser.add_argument("--coordinate-scale", type=float, required=True)
    parser.add_argument("--tile-size", type=int, default=0)
    parser.add_argument("--tile-overlap", type=int, default=0)
    parser.add_argument("--tracker-distance", type=float, default=100)
    parser.add_argument("--max-missed-frames", type=int, default=12)
    parser.add_argument("--match-distance", type=float, default=80)
    args = parser.parse_args()
    if (
        args.tile_size < 0
        or args.tile_overlap < 0
        or (args.tile_size == 0 and args.tile_overlap)
        or (args.tile_size and args.tile_overlap >= args.tile_size)
    ):
        parser.error("tile-size deve ser positivo e tile-overlap menor que tile-size")

    with args.ground_truth.open(encoding="utf-8") as source:
        labels = read_mot_positions(
            source,
            first_frame=args.first_frame,
            last_frame=args.last_frame,
            coordinate_scale=args.coordinate_scale,
        )
    detector = YoloXOnnxDetector(str(args.model))
    if args.tile_size:
        detector = TiledDetector(detector, args.tile_size, args.tile_overlap)
    tracker = CentroidTracker(args.tracker_distance, args.max_missed_frames)
    score = score_mot_tracking_video(
        args.video,
        detector,
        tracker,
        labels,
        first_frame=args.first_frame,
        last_frame=args.last_frame,
        max_match_distance=args.match_distance,
    )
    print(json.dumps({**asdict(score), "recall": score.recall}))


if __name__ == "__main__":
    main()
