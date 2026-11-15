"""Derive passage totals from versioned events, independent of inference."""

from __future__ import annotations

import argparse
import json
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class PassageTotals:
    _events: dict[str, dict] = field(default_factory=dict)
    _counts: dict[tuple[str, str, str], dict[str, int]] = field(default_factory=dict)

    def record(self, event: dict) -> None:
        if event.get("schema_version") != 2 or event.get("event_type") != "passage":
            raise ValueError("Esperado evento passage v2")
        for key in ("event_id", "source_id", "session_id", "access_id"):
            if not isinstance(event.get(key), str) or not event[key].strip():
                raise ValueError(f"{key} obrigatório")
        data = event.get("data")
        if not isinstance(data, dict) or data.get("direction") not in ("in", "out"):
            raise ValueError("direction deve ser in ou out")
        # Snapshot prevents callers mutating the deduplication evidence.
        snapshot = json.loads(json.dumps(event, allow_nan=False))
        event_id = event["event_id"]
        if event_id in self._events:
            if self._events[event_id] != snapshot:
                raise ValueError("event_id reutilizado com conteúdo diferente")
            return
        key = (event["source_id"], event["session_id"], event["access_id"])
        counts = self._counts.setdefault(key, {"in": 0, "out": 0})
        counts[data["direction"]] += 1
        self._events[event_id] = snapshot

    def rows(self) -> list[dict]:
        return [
            dict(source_id=source, session_id=session, access_id=access, **counts)
            for (source, session, access), counts in sorted(self._counts.items())
        ]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("events", type=Path, nargs="?", help="JSONL de eventos v2")
    parser.add_argument("--outbox", type=Path, help="Consultar fila SQLite em modo somente leitura")
    args = parser.parse_args()
    totals = PassageTotals()
    if bool(args.events) == bool(args.outbox):
        parser.error("Informe JSONL ou --outbox")
    try:
        if args.outbox:
            db = sqlite3.connect(args.outbox.resolve().as_uri() + "?mode=ro", uri=True)
            try:
                for (payload,) in db.execute("SELECT payload FROM outbox ORDER BY rowid"):
                    event = json.loads(payload)
                    if event.get("event_type") == "passage":
                        totals.record(event)
            finally:
                db.close()
            print(json.dumps(totals.rows(), ensure_ascii=False))
            return
        with args.events.open() as source:
            for line in source:
                if line.strip():
                    event = json.loads(line)
                    if not isinstance(event, dict):
                        raise ValueError("Evento deve ser objeto JSON")
                    if event.get("event_type") == "passage":
                        totals.record(event)
        print(json.dumps(totals.rows(), ensure_ascii=False))
    except (OSError, ValueError, sqlite3.Error) as error:
        parser.error(str(error))


if __name__ == "__main__":
    main()
