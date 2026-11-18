"""Evaluate the built-in tracker with ideal detections from MOT ground truth."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path

from fazenda_cv.mot_data import read_mot_positions, replay_mot_labels_as_detections
from fazenda_cv.tracking import CentroidTracker
from fazenda_cv.tracking_evaluation import score_tracks


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ground_truth", type=Path, help="MOTChallenge gt.txt")
    parser.add_argument("--first-frame", type=int, required=True)
    parser.add_argument("--last-frame", type=int, required=True)
    parser.add_argument("--tracker-distance", type=float, default=100)
    parser.add_argument("--max-missed-frames", type=int, default=12)
    parser.add_argument("--match-distance", type=float, default=80)
    args = parser.parse_args()

    if args.tracker_distance <= 0 or args.max_missed_frames < 0:
        parser.error("tracker-distance deve ser positivo e max-missed-frames não negativo")
    with args.ground_truth.open(encoding="utf-8") as source:
        labels = read_mot_positions(
            source, first_frame=args.first_frame, last_frame=args.last_frame
        )
    tracker = CentroidTracker(args.tracker_distance, args.max_missed_frames)
    frames = replay_mot_labels_as_detections(
        labels, tracker, first_frame=args.first_frame, last_frame=args.last_frame
    )
    score = score_tracks(frames, max_distance=args.match_distance)
    print(
        json.dumps(
            {
                "protocol": "ideal_detections_from_ground_truth",
                "first_frame": args.first_frame,
                "last_frame": args.last_frame,
                "tracker_distance": args.tracker_distance,
                "max_missed_frames": args.max_missed_frames,
                "match_distance": args.match_distance,
                **asdict(score),
                "recall": score.recall,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
