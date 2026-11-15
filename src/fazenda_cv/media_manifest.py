"""Validation of provenance metadata for local evaluation media."""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

FIELDS = (
    "media_id",
    "media_type",
    "source_url",
    "author",
    "license",
    "usage_terms",
    "sha256",
    "environment",
    "split",
    "duration_seconds",
    "fps",
    "width",
    "height",
    "lighting",
    "occlusion",
)


@dataclass(frozen=True, slots=True)
class MediaRecord:
    media_id: str
    media_type: str
    source_url: str
    author: str
    license: str
    usage_terms: str
    sha256: str
    environment: str
    split: str
    duration_seconds: float | None
    fps: float | None
    width: int | None
    height: int | None
    lighting: str
    occlusion: str


def _positive_number(value: str, field: str, row: int, kind: type) -> float | int | None:
    if not value:
        return None
    try:
        result = kind(value)
    except ValueError as error:
        raise ValueError(f"Linha {row}: {field} deve ser numérico") from error
    if result <= 0:
        raise ValueError(f"Linha {row}: {field} deve ser positivo")
    return result


def load_manifest(path: str | Path) -> list[MediaRecord]:
    """Load a CSV manifest, rejecting incomplete or ambiguous provenance."""
    with Path(path).open(newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)
        if reader.fieldnames is None or set(reader.fieldnames) != set(FIELDS):
            raise ValueError(f"Cabeçalhos esperados: {', '.join(FIELDS)}")
        records: list[MediaRecord] = []
        seen_ids: set[str] = set()
        seen_hashes: dict[str, str] = {}
        for row_number, raw in enumerate(reader, start=2):
            if None in raw:
                raise ValueError(f"Linha {row_number}: colunas adicionais inesperadas")
            row = {key: (value or "").strip() for key, value in raw.items()}
            media_id = row["media_id"]
            if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", media_id):
                raise ValueError(f"Linha {row_number}: media_id inválido")
            if media_id in seen_ids:
                raise ValueError(f"Linha {row_number}: media_id duplicado")
            seen_ids.add(media_id)
            if row["media_type"] not in {"photo", "video"}:
                raise ValueError(f"Linha {row_number}: media_type deve ser photo ou video")
            parsed_url = urlparse(row["source_url"])
            if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
                raise ValueError(f"Linha {row_number}: source_url deve ser HTTP(S)")
            for field in ("author", "license", "usage_terms", "environment"):
                if not row[field]:
                    raise ValueError(f"Linha {row_number}: {field} é obrigatório")
            if not re.fullmatch(r"[a-fA-F0-9]{64}", row["sha256"]):
                raise ValueError(f"Linha {row_number}: sha256 inválido")
            if row["split"] not in {"tuning", "evaluation"}:
                raise ValueError(f"Linha {row_number}: split deve ser tuning ou evaluation")
            digest = row["sha256"].lower()
            if digest in seen_hashes and seen_hashes[digest] != row["split"]:
                raise ValueError(f"Linha {row_number}: mídia duplicada em divisões diferentes")
            seen_hashes[digest] = row["split"]
            duration = _positive_number(
                row["duration_seconds"], "duration_seconds", row_number, float
            )
            fps = _positive_number(row["fps"], "fps", row_number, float)
            width = _positive_number(row["width"], "width", row_number, int)
            height = _positive_number(row["height"], "height", row_number, int)
            if row["media_type"] == "video" and (duration is None or fps is None):
                raise ValueError(f"Linha {row_number}: vídeo exige duração e FPS")
            if width is None or height is None:
                raise ValueError(f"Linha {row_number}: resolução é obrigatória")
            records.append(
                MediaRecord(
                    media_id,
                    row["media_type"],
                    row["source_url"],
                    row["author"],
                    row["license"],
                    row["usage_terms"],
                    digest,
                    row["environment"],
                    row["split"],
                    duration,
                    fps,
                    width,
                    height,
                    row["lighting"],
                    row["occlusion"],
                )
            )
    return records
