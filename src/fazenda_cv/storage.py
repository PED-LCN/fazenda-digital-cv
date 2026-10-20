from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from fazenda_cv.domain import MonitorEvent, MonitoringSession


class EventStore:
    def __init__(self, database: str | Path) -> None:
        self.database = str(database)
        Path(self.database).parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.executescript(
                """
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS events (
                    event_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    occurred_at TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    acknowledged INTEGER NOT NULL DEFAULT 0,
                    synced INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS idx_events_session_time
                    ON events(session_id, occurred_at DESC);
                CREATE INDEX IF NOT EXISTS idx_events_outbox
                    ON events(synced, created_at);
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    expected_passages INTEGER NOT NULL,
                    allowed_from TEXT NOT NULL,
                    allowed_until TEXT NOT NULL,
                    tolerance INTEGER NOT NULL,
                    started_at TEXT NOT NULL,
                    ended_at TEXT,
                    in_count INTEGER NOT NULL DEFAULT 0,
                    out_count INTEGER NOT NULL DEFAULT 0,
                    active INTEGER NOT NULL,
                    time_zone TEXT NOT NULL DEFAULT 'America/Sao_Paulo'
                );
                """
            )
            session_columns = {
                row["name"] for row in connection.execute("PRAGMA table_info(sessions)").fetchall()
            }
            if "time_zone" not in session_columns:
                connection.execute(
                    "ALTER TABLE sessions ADD COLUMN time_zone TEXT NOT NULL "
                    "DEFAULT 'America/Sao_Paulo'"
                )

    def save_session(self, session: MonitoringSession) -> None:
        with self._connect() as connection:
            self._save_session(connection, session)

    def save_session_with_events(
        self, session: MonitoringSession, events: list[MonitorEvent]
    ) -> None:
        with self._connect() as connection:
            for event in events:
                self._insert_event(connection, event)
            self._save_session(connection, session)

    @staticmethod
    def _save_session(connection: sqlite3.Connection, session: MonitoringSession) -> None:
        connection.execute(
            """INSERT INTO sessions(
                    session_id, expected_passages, allowed_from, allowed_until, tolerance,
                    started_at, ended_at, in_count, out_count, active, time_zone
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    ended_at=excluded.ended_at, in_count=excluded.in_count,
                    out_count=excluded.out_count, active=excluded.active""",
            (
                session.session_id,
                session.expected_passages,
                session.allowed_from.isoformat(),
                session.allowed_until.isoformat(),
                session.tolerance,
                session.started_at.isoformat(),
                session.ended_at.isoformat() if session.ended_at else None,
                session.in_count,
                session.out_count,
                int(session.active),
                session.time_zone,
            ),
        )

    @staticmethod
    def _insert_event(connection: sqlite3.Connection, event: MonitorEvent) -> None:
        payload = json.dumps(event.to_dict(), separators=(",", ":"))
        connection.execute(
            "INSERT OR IGNORE INTO events(event_id, session_id, event_type, occurred_at, payload) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                event.event_id,
                event.session_id,
                event.event_type.value,
                event.occurred_at.isoformat(),
                payload,
            ),
        )

    def load_active_session(self) -> MonitoringSession | None:
        from datetime import datetime, time

        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM sessions WHERE active = 1 ORDER BY started_at DESC LIMIT 1"
            ).fetchone()
        if row is None:
            return None
        return MonitoringSession(
            expected_passages=row["expected_passages"],
            allowed_from=time.fromisoformat(row["allowed_from"]),
            allowed_until=time.fromisoformat(row["allowed_until"]),
            tolerance=row["tolerance"],
            session_id=row["session_id"],
            started_at=datetime.fromisoformat(row["started_at"]),
            ended_at=datetime.fromisoformat(row["ended_at"]) if row["ended_at"] else None,
            in_count=row["in_count"],
            out_count=row["out_count"],
            active=True,
            time_zone=row["time_zone"],
        )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database, timeout=10)
        connection.row_factory = sqlite3.Row
        return connection

    def add(self, event: MonitorEvent) -> None:
        with self._connect() as connection:
            self._insert_event(connection, event)

    def list(self, limit: int = 100, session_id: str | None = None) -> list[dict[str, Any]]:
        query = "SELECT payload, acknowledged, synced FROM events"
        parameters: list[Any] = []
        if session_id:
            query += " WHERE session_id = ?"
            parameters.append(session_id)
        query += " ORDER BY occurred_at DESC LIMIT ?"
        parameters.append(max(1, min(limit, 500)))
        with self._connect() as connection:
            rows = connection.execute(query, parameters).fetchall()
        return [
            {
                **json.loads(row["payload"]),
                "acknowledged": bool(row["acknowledged"]),
                "synced": bool(row["synced"]),
            }
            for row in rows
        ]

    def acknowledge(self, event_id: str) -> bool:
        with self._connect() as connection:
            result = connection.execute(
                "UPDATE events SET acknowledged = 1 WHERE event_id = ?", (event_id,)
            )
            return result.rowcount > 0

    def pending(self, limit: int = 100) -> list[dict[str, Any]]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT payload FROM events WHERE synced = 0 ORDER BY created_at LIMIT ?", (limit,)
            ).fetchall()
        return [json.loads(row["payload"]) for row in rows]

    def mark_synced(self, event_id: str) -> None:
        with self._connect() as connection:
            connection.execute("UPDATE events SET synced = 1 WHERE event_id = ?", (event_id,))

    def counts(self, session_id: str | None = None) -> dict[str, int]:
        where = " WHERE session_id = ?" if session_id else ""
        parameters = (session_id,) if session_id else ()
        with self._connect() as connection:
            rows = connection.execute(
                f"SELECT event_type, direction, COUNT(*) as amount FROM "
                f"(SELECT event_type, json_extract(payload, '$.direction') AS direction, "
                "session_id "
                f"FROM events){where} GROUP BY event_type, direction",
                parameters,
            ).fetchall()
        result = {"in": 0, "out": 0, "after_hours": 0, "count_mismatch": 0, "passage": 0}
        for row in rows:
            if row["event_type"] == "passage":
                result[row["direction"] or "passage"] += row["amount"]
                result["passage"] += row["amount"]
            else:
                result[row["event_type"]] = row["amount"]
        return result
