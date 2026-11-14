"""Operational evidence from a video run, without claiming model accuracy."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class RunReport:
    source_id: str
    detector_version: str
    frames: int = 0
    frames_with_cattle: int = 0
    detections: int = 0
    max_cattle_in_frame: int = 0
    passage_events: int = 0

    def record_frame(self, cattle_count: int, passage_count: int) -> None:
        if cattle_count < 0 or passage_count < 0:
            raise ValueError("Contagens não podem ser negativas")
        self.frames += 1
        self.frames_with_cattle += int(cattle_count > 0)
        self.detections += cattle_count
        self.max_cattle_in_frame = max(self.max_cattle_in_frame, cattle_count)
        self.passage_events += passage_count

    def save(self, path: Path, elapsed_seconds: float) -> None:
        if elapsed_seconds <= 0:
            raise ValueError("Tempo de execução inválido")
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "source_id": self.source_id,
            "detector_version": self.detector_version,
            "frames": self.frames,
            "frames_with_cattle": self.frames_with_cattle,
            "detections": self.detections,
            "max_cattle_in_frame": self.max_cattle_in_frame,
            "passage_events": self.passage_events,
            "processing_fps": round(self.frames / elapsed_seconds, 2),
            "validation_level": "operational_smoke_test",
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
