from __future__ import annotations

import logging
import threading
from dataclasses import replace
from datetime import UTC, datetime, time
from typing import Protocol

import numpy as np

from fazenda_cv.counter import PassageCounter
from fazenda_cv.domain import CountLine, Detection, EventType, MonitorEvent, MonitoringSession
from fazenda_cv.evidence import EvidenceStore
from fazenda_cv.storage import EventStore
from fazenda_cv.tracking import CentroidTracker

logger = logging.getLogger(__name__)


class Siren(Protocol):
    def trigger(self, reason: str, event_id: str) -> None: ...

    def silence(self) -> None: ...

    def status(self) -> dict[str, object]: ...


class SimulatedSiren:
    def __init__(self, max_seconds: int = 30) -> None:
        self.max_seconds = max_seconds
        self.active = False
        self.reason: str | None = None
        self.event_id: str | None = None
        self.triggered_at: datetime | None = None
        self.silenced = False
        self._lock = threading.Lock()

    def trigger(self, reason: str, event_id: str) -> None:
        with self._lock:
            self.active = True
            self.reason = reason
            self.event_id = event_id
            self.triggered_at = datetime.now(UTC)
            self.silenced = False

    def silence(self) -> None:
        with self._lock:
            self.active = False
            self.silenced = True

    def status(self) -> dict[str, object]:
        with self._lock:
            active = self.active
            if active and self.triggered_at:
                active = (datetime.now(UTC) - self.triggered_at).total_seconds() < self.max_seconds
                self.active = active
            return {"active": active, "reason": self.reason, "silenced": self.silenced}


class MonitorService:
    def __init__(
        self,
        store: EventStore,
        siren: Siren | None = None,
        farm_id: str = "fazenda-local",
        camera_id: str = "camera-1",
        evidence_store: EvidenceStore | None = None,
        time_zone: str = "America/Sao_Paulo",
        count_line: CountLine | None = None,
    ) -> None:
        self.store = store
        self.siren = siren or SimulatedSiren()
        self.session = store.load_active_session()
        if self.session:
            recovered_counts = store.counts(self.session.session_id)
            self.session.in_count = recovered_counts["in"]
            self.session.out_count = recovered_counts["out"]
        self.farm_id = farm_id
        self.camera_id = camera_id
        self.evidence_store = evidence_store
        self.time_zone = time_zone
        self.count_line = count_line or CountLine()
        self.camera_state = "idle"
        self.last_frame_at: str | None = None
        self.model_version = "not-loaded"
        self.tracker = CentroidTracker()
        self.counter = PassageCounter(self.count_line)
        self._lock = threading.RLock()

    def start_session(
        self, expected_passages: int, allowed_from: time, allowed_until: time, tolerance: int
    ) -> MonitoringSession:
        with self._lock:
            if self.session and self.session.active:
                raise ValueError("Já existe uma sessão ativa")
            if expected_passages < 0 or tolerance < 0:
                raise ValueError("Quantidade e tolerância devem ser positivas")
            self.session = MonitoringSession(
                expected_passages=expected_passages,
                allowed_from=allowed_from,
                allowed_until=allowed_until,
                tolerance=tolerance,
                time_zone=self.time_zone,
            )
            self.store.save_session(self.session)
            self.tracker = CentroidTracker()
            self.counter = PassageCounter(self.count_line)
            return self.session

    def process_frame(
        self,
        frame: np.ndarray,
        detections: list[Detection],
        farm_id: str | None = None,
        camera_id: str | None = None,
        model_version: str = "test-detector",
        moment: datetime | None = None,
    ) -> list[MonitorEvent]:
        with self._lock:
            self.camera_state = "streaming"
            self.last_frame_at = (moment or datetime.now(UTC)).isoformat()
            self.model_version = model_version
            session = self.session
            if not session or not session.active:
                return []
            tracks = self.tracker.update(detections)
            events = self.counter.update(
                tracks,
                (frame.shape[1], frame.shape[0]),
                session,
                farm_id or self.farm_id,
                camera_id or self.camera_id,
                model_version,
                moment,
            )
            persisted_events: list[MonitorEvent] = []
            evidence_ref: str | None = None
            if events and self.evidence_store:
                first_event_id = events[0].event_id
                try:
                    evidence_id = self.evidence_store.save(first_event_id, frame)
                    if evidence_id:
                        evidence_ref = f"evidence/{evidence_id}.jpg"
                except OSError:
                    # Evidence is optional; a filesystem error must not lose a passage event.
                    logger.exception(
                        "Não foi possível salvar evidência do evento %s", first_event_id
                    )
                    evidence_ref = None
            for event in events:
                if evidence_ref:
                    event = replace(
                        event,
                        details={**event.details, "evidence_ref": evidence_ref},
                    )
                persisted_events.append(event)
            if persisted_events:
                self.store.save_session_with_events(session, persisted_events)
            for event in persisted_events:
                if event.event_type is EventType.AFTER_HOURS:
                    self.siren.trigger("after_hours", event.event_id)
            self.counter.retain_tracks(self.tracker.active_ids)
            return persisted_events

    def stop_session(self, moment: datetime | None = None) -> MonitoringSession:
        with self._lock:
            if not self.session or not self.session.active:
                raise ValueError("Não existe sessão ativa")
            session = self.session
            session.active = False
            session.ended_at = moment or datetime.now(UTC)
            difference = abs(session.total_count - session.expected_passages)
            mismatch_event: MonitorEvent | None = None
            if difference > session.tolerance:
                mismatch_event = MonitorEvent(
                    event_type=EventType.COUNT_MISMATCH,
                    farm_id=self.farm_id,
                    camera_id=self.camera_id,
                    session_id=session.session_id,
                    occurred_at=session.ended_at,
                    model_version=self.model_version,
                    details={
                        "expected_passages": session.expected_passages,
                        "observed_passages": session.total_count,
                        "difference": difference,
                        "alert": True,
                    },
                )
                self.store.save_session_with_events(session, [mismatch_event])
                self.siren.trigger("count_mismatch", mismatch_event.event_id)
            else:
                self.store.save_session(session)
            return session

    def status(self) -> dict[str, object]:
        with self._lock:
            session = self.session
            counts = self.store.counts(session.session_id if session else None)
            return {
                "camera_state": self.camera_state,
                "last_frame_at": self.last_frame_at,
                "model_version": self.model_version,
                "count_line": {"start": self.count_line.start, "end": self.count_line.end},
                "session": None
                if not session
                else {
                    "session_id": session.session_id,
                    "active": session.active,
                    "expected_passages": session.expected_passages,
                    "in_count": session.in_count,
                    "out_count": session.out_count,
                    "total_count": session.total_count,
                    "tolerance": session.tolerance,
                    "started_at": session.started_at.isoformat(),
                    "ended_at": session.ended_at.isoformat() if session.ended_at else None,
                },
                "counts": counts,
                "siren": self.siren.status(),
                "pending_sync": len(self.store.pending()),
            }
