"""Per-access line and source configuration for cattle passages."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from fazenda_cv.domain import CountLine


@dataclass(frozen=True, slots=True)
class AccessConfig:
    access_id: str
    source_id: str
    line: CountLine


def load_access_configs(path: str | Path) -> dict[str, AccessConfig]:
    """Read two independently calibrated accesses from JSON."""
    with Path(path).open(encoding="utf-8") as file:
        document = json.load(file)
    if not isinstance(document, dict) or set(document) != {"accesses"}:
        raise ValueError("Configuração exige apenas a chave accesses")
    items = document["accesses"]
    if not isinstance(items, list) or len(items) != 2:
        raise ValueError("Configure os acessos curral e ordenha")
    configs = {}
    for item in items:
        if not isinstance(item, dict) or set(item) != {"access_id", "source_id", "line"}:
            raise ValueError("Cada acesso exige access_id, source_id e line")
        access_id, source_id = item["access_id"], item["source_id"]
        if access_id not in {"curral", "ordenha"} or not isinstance(source_id, str):
            raise ValueError("Acesso ou fonte inválidos")
        if not source_id.strip():
            raise ValueError("source_id não pode ser vazio")
        coordinates = item["line"]
        if (
            not isinstance(coordinates, list)
            or len(coordinates) != 4
            or any(
                isinstance(value, bool) or not isinstance(value, (int, float))
                for value in coordinates
            )
        ):
            raise ValueError("line exige quatro coordenadas numéricas normalizadas")
        if access_id in configs:
            raise ValueError("access_id duplicado")
        configs[access_id] = AccessConfig(
            access_id,
            source_id.strip(),
            CountLine((coordinates[0], coordinates[1]), (coordinates[2], coordinates[3])),
        )
    if set(configs) != {"curral", "ordenha"}:
        raise ValueError("Configure os acessos curral e ordenha")
    return configs
