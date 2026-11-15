"""Ground truth for cattle presence and monitoring episodes."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from fazenda_cv.media_manifest import MediaRecord

EPISODE_KINDS = frozenset({"crowding", "immobility", "boundary_exit", "outside_area"})


@dataclass(frozen=True, slots=True)
class BoxAnnotation:
    media_id: str
    frame_ms: int
    region_id: str
    xyxy: tuple[float, float, float, float]


@dataclass(frozen=True, slots=True)
class EpisodeAnnotation:
    media_id: str
    kind: str
    region_id: str
    start_ms: int
    end_ms: int
    positive: bool


@dataclass(frozen=True, slots=True)
class MonitoringAnnotations:
    boxes: list[BoxAnnotation]
    episodes: list[EpisodeAnnotation]


def _offset(value: object, duration_ms: int, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= duration_ms:
        raise ValueError(f"{field} fora do vídeo")
    return value


def load_monitoring_annotations(
    path: str | Path, media: list[MediaRecord]
) -> MonitoringAnnotations:
    """Read and validate boxes and positive/negative temporal episodes."""
    catalog = {record.media_id: record for record in media}
    with Path(path).open(encoding="utf-8") as file:
        document = json.load(file)
    if not isinstance(document, dict) or set(document) != {"boxes", "episodes"}:
        raise ValueError("Anotações exigem boxes e episodes")
    if not isinstance(document["boxes"], list) or not isinstance(document["episodes"], list):
        raise ValueError("boxes e episodes devem ser listas")
    boxes = []
    for item in document["boxes"]:
        if not isinstance(item, dict) or set(item) != {"media_id", "frame_ms", "region_id", "xyxy"}:
            raise ValueError("Caixa exige media_id, frame_ms, region_id e xyxy")
        record = catalog.get(item["media_id"])
        if record is None:
            raise ValueError("Caixa referencia mídia não catalogada")
        duration = round((record.duration_seconds or 0) * 1000)
        frame_ms = _offset(item["frame_ms"], duration, "frame_ms")
        coords = item["xyxy"]
        if (
            not isinstance(coords, list)
            or len(coords) != 4
            or any(isinstance(x, bool) or not isinstance(x, (int, float)) for x in coords)
            or not (0 <= coords[0] < coords[2] <= 1 and 0 <= coords[1] < coords[3] <= 1)
        ):
            raise ValueError("xyxy deve conter caixa normalizada válida")
        if not isinstance(item["region_id"], str) or not item["region_id"].strip():
            raise ValueError("region_id é obrigatório")
        boxes.append(BoxAnnotation(item["media_id"], frame_ms, item["region_id"], tuple(coords)))
    episodes = []
    for item in document["episodes"]:
        if not isinstance(item, dict) or set(item) != {
            "media_id",
            "kind",
            "region_id",
            "start_ms",
            "end_ms",
            "positive",
        }:
            raise ValueError("Episódio exige mídia, tipo, região, intervalo e rótulo")
        record = catalog.get(item["media_id"])
        if record is None or record.media_type != "video":
            raise ValueError("Episódio exige vídeo catalogado")
        if item["kind"] not in EPISODE_KINDS:
            raise ValueError("Tipo de episódio inválido")
        if not isinstance(item["region_id"], str) or not item["region_id"].strip():
            raise ValueError("region_id é obrigatório")
        duration = round((record.duration_seconds or 0) * 1000)
        start = _offset(item["start_ms"], duration, "start_ms")
        end = _offset(item["end_ms"], duration, "end_ms")
        if end <= start or not isinstance(item["positive"], bool):
            raise ValueError("Intervalo ou rótulo de episódio inválido")
        episodes.append(
            EpisodeAnnotation(
                item["media_id"],
                item["kind"],
                item["region_id"],
                start,
                end,
                item["positive"],
            )
        )
    return MonitoringAnnotations(boxes, episodes)
