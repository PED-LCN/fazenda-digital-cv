"""Persistent, at-least-once delivery, run separately from video inference."""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen


class EventOutbox:
    def __init__(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        with self.connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS outbox (
                event_id TEXT PRIMARY KEY, payload TEXT NOT NULL,
                attempts INTEGER NOT NULL DEFAULT 0, next_attempt REAL NOT NULL DEFAULT 0,
                delivered INTEGER NOT NULL DEFAULT 0)""")

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        db = sqlite3.connect(self.path, timeout=5)
        try:
            with db:
                yield db
        finally:
            db.close()

    def enqueue(self, payload: dict) -> None:
        event_id = payload.get("event_id")
        if not isinstance(event_id, str) or not event_id.strip():
            raise ValueError("event_id é obrigatório")
        if payload.get("schema_version") != 2:
            raise ValueError("Webhook exige schema_version 2")
        encoded = json.dumps(payload, sort_keys=True, allow_nan=False)
        with self.connect() as db:
            existing = db.execute(
                "SELECT payload FROM outbox WHERE event_id=?", (event_id,)
            ).fetchone()
            if existing and existing[0] != encoded:
                raise ValueError("event_id reutilizado com outro payload")
            db.execute(
                "INSERT OR IGNORE INTO outbox(event_id,payload) VALUES (?,?)", (event_id, encoded)
            )

    def deliver_once(
        self, url: str, *, token: str | None = None, now: float | None = None, timeout: float = 5
    ) -> int:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username:
            raise ValueError("URL HTTP(S) sem credenciais é obrigatória")
        moment = time.time() if now is None else now
        with self.connect() as db:
            rows = db.execute(
                """SELECT event_id,payload,attempts FROM outbox
                WHERE delivered=0 AND next_attempt<=? ORDER BY rowid LIMIT 100""",
                (moment,),
            ).fetchall()
        delivered = 0
        for event_id, payload, attempts in rows:
            headers = {"Content-Type": "application/json", "Idempotency-Key": event_id}
            if token:
                headers["Authorization"] = f"Bearer {token}"
            try:
                request = Request(url, payload.encode(), headers, method="POST")
                with urlopen(request, timeout=timeout) as response:
                    if not 200 <= response.status < 300:
                        raise OSError("Resposta sem confirmação")
            except (OSError, ValueError):
                delay = min(300, 2 ** min(attempts + 1, 9))
                with self.connect() as db:
                    db.execute(
                        "UPDATE outbox SET attempts=attempts+1,next_attempt=? WHERE event_id=?",
                        (moment + delay, event_id),
                    )
            else:
                with self.connect() as db:
                    db.execute("UPDATE outbox SET delivered=1 WHERE event_id=?", (event_id,))
                delivered += 1
        return delivered


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--import-jsonl", type=Path)
    parser.add_argument("--url", default=os.environ.get("CV_WEBHOOK_URL"))
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    outbox = EventOutbox(args.database)
    if args.import_jsonl:
        with args.import_jsonl.open() as source:
            for line in source:
                if line.strip():
                    outbox.enqueue(json.loads(line))
    if not args.url:
        parser.error("Informe --url ou CV_WEBHOOK_URL")
    try:
        while True:
            count = outbox.deliver_once(args.url, token=os.environ.get("CV_WEBHOOK_TOKEN"))
            print(json.dumps({"delivered": count}), flush=True)
            if args.once:
                break
            time.sleep(1)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
