"""Detection recall and post-acquisition retention against frame-aligned MOT IDs."""

from __future__ import annotations

from dataclasses import dataclass

from fazenda_cv.domain import Detection
from fazenda_cv.model_qualification import _iou
from fazenda_cv.mot_boxes import MotBox


@dataclass(frozen=True)
class FrameObservation:
    frame: int
    labels: list[MotBox]
    detections: list[Detection]


def score_sequence(frames: list[FrameObservation], *, iou_threshold: float = 0.5) -> dict:
    if not 0 < iou_threshold <= 1:
        raise ValueError("IoU deve estar em (0, 1]")
    if any(b.frame <= a.frame for a, b in zip(frames, frames[1:], strict=False)):
        raise ValueError("Quadros devem ser únicos e crescentes")
    tracks: dict[int, list[tuple[int, bool]]] = {}
    tp = fp = fn = 0
    for sample in frames:
        if len({box.object_id for box in sample.labels}) != len(sample.labels):
            raise ValueError("ID GT duplicado")
        matched: set[int] = set()
        for detection in sorted(sample.detections, key=lambda box: box.confidence, reverse=True):
            candidates = [
                (_iou(box.xyxy, detection), i)
                for i, box in enumerate(sample.labels)
                if i not in matched
            ]
            if candidates:
                overlap, index = max(candidates)
                if overlap >= iou_threshold:
                    matched.add(index)
        tp += len(matched)
        fp += len(sample.detections) - len(matched)
        fn += len(sample.labels) - len(matched)
        for i, box in enumerate(sample.labels):
            tracks.setdefault(box.object_id, []).append((sample.frame, i in matched))
    acquired = retained = opportunities = pair_hits = pair_opportunities = 0
    per_track = []
    for identity, samples in sorted(tracks.items()):
        first = next((i for i, (_, hit) in enumerate(samples) if hit), None)
        after = [] if first is None else samples[first + 1 :]
        hits = sum(hit for _, hit in after)
        acquired += first is not None
        retained += hits
        opportunities += len(after)
        for (previous_frame, previous_hit), (current_frame, current_hit) in zip(
            samples, samples[1:], strict=False
        ):
            if previous_hit and current_frame == previous_frame + 1:
                pair_opportunities += 1
                pair_hits += current_hit
        per_track.append(
            dict(
                object_id=identity,
                visible=len(samples),
                matched=sum(hit for _, hit in samples),
                first_match_frame=None if first is None else samples[first][0],
                retained=hits,
                opportunities=len(after),
                retention=None if not after else hits / len(after),
            )
        )
    return dict(
        true_positive=tp,
        false_positive=fp,
        false_negative=fn,
        recall=tp / (tp + fn) if tp + fn else None,
        precision=tp / (tp + fp) if tp + fp else None,
        acquired_tracks=acquired,
        labelled_tracks=len(tracks),
        retained=retained,
        retention_opportunities=opportunities,
        retention=retained / opportunities if opportunities else None,
        consecutive_hits=pair_hits,
        consecutive_opportunities=pair_opportunities,
        consecutive_retention=pair_hits / pair_opportunities if pair_opportunities else None,
        tracks=per_track,
    )


def combine_scores(scores: list[dict]) -> dict:
    keys = (
        "true_positive",
        "false_positive",
        "false_negative",
        "acquired_tracks",
        "labelled_tracks",
        "retained",
        "retention_opportunities",
        "consecutive_hits",
        "consecutive_opportunities",
    )
    result = {key: sum(score[key] for score in scores) for key in keys}
    for name, numerator, denominator in [
        ("recall", result["true_positive"], result["true_positive"] + result["false_negative"]),
        ("precision", result["true_positive"], result["true_positive"] + result["false_positive"]),
        ("retention", result["retained"], result["retention_opportunities"]),
        ("consecutive_retention", result["consecutive_hits"], result["consecutive_opportunities"]),
    ]:
        result[name] = numerator / denominator if denominator else None
    result["target_met"] = (
        result["recall"] is not None
        and result["recall"] >= 0.6
        and result["retention"] is not None
        and result["retention"] >= 0.7
    )
    return result
