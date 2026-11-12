"""Ground truth for cattle passages in recorded video."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

from fazenda_cv.domain import Direction
from fazenda_cv.media_manifest import MediaRecord

FIELDS = ("media_id", "access_id", "video_offset_ms", "direction", "ambiguous")


@dataclass(frozen=True, slots=True)
class PassageAnnotation:
    media_id: str
    access_id: str
    video_offset_ms: int
    direction: Direction
    ambiguous: bool


def load_passage_annotations(path: str | Path, media: list[MediaRecord]) -> list[PassageAnnotation]:
    """Load labels, checking that every passage points to a catalogued video."""
    videos = {record.media_id: record for record in media if record.media_type == "video"}
    with Path(path).open(newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)
        if reader.fieldnames is None or tuple(reader.fieldnames) != FIELDS:
            raise ValueError(f"Cabeçalhos esperados: {', '.join(FIELDS)}")
        annotations = []
        seen: set[tuple[str, str, int, str]] = set()
        for row_number, row in enumerate(reader, start=2):
            if None in row:
                raise ValueError(f"Linha {row_number}: colunas adicionais inesperadas")
            values = {key: (value or "").strip() for key, value in row.items()}
            media_id = values["media_id"]
            video = videos.get(media_id)
            if video is None:
                raise ValueError(f"Linha {row_number}: vídeo não catalogado: {media_id}")
            access_id = values["access_id"]
            if access_id not in {"curral", "ordenha"}:
                raise ValueError(f"Linha {row_number}: acesso deve ser curral ou ordenha")
            try:
                offset_ms = int(values["video_offset_ms"])
            except ValueError as error:
                raise ValueError(f"Linha {row_number}: video_offset_ms inválido") from error
            if offset_ms < 0 or offset_ms > round((video.duration_seconds or 0) * 1000):
                raise ValueError(f"Linha {row_number}: posição fora do vídeo")
            try:
                direction = Direction(values["direction"])
            except ValueError as error:
                raise ValueError(f"Linha {row_number}: direção deve ser in ou out") from error
            if values["ambiguous"] not in {"true", "false"}:
                raise ValueError(f"Linha {row_number}: ambiguous deve ser true ou false")
            key = (media_id, access_id, offset_ms, direction.value)
            if key in seen:
                raise ValueError(f"Linha {row_number}: passagem duplicada")
            seen.add(key)
            annotations.append(
                PassageAnnotation(
                    media_id, access_id, offset_ms, direction, values["ambiguous"] == "true"
                )
            )
    return annotations
