from datetime import UTC, datetime, time
from time import monotonic, sleep

import cv2
import numpy as np

from fazenda_cv.detection import GreenMarkerDetector
from fazenda_cv.domain import Detection, Direction, EventType
from fazenda_cv.evidence import EvidenceStore
from fazenda_cv.service import MonitorService, SimulatedSiren
from fazenda_cv.storage import EventStore
from fazenda_cv.video import VideoWorker


def frame() -> np.ndarray:
    return np.zeros((100, 100, 3), dtype=np.uint8)


def detection(x: float, y: float = 50) -> Detection:
    return Detection(x - 5, y - 5, x + 5, y + 5, 0.9, 19)


def test_count_line_emits_one_inbound_event_when_track_crosses(tmp_path) -> None:
    service = MonitorService(EventStore(tmp_path / "events.sqlite3"))
    session = service.start_session(1, time(0), time(23, 59), 0)
    service.process_frame(frame(), [detection(35)], moment=datetime(2026, 10, 20, 12, tzinfo=UTC))
    events = service.process_frame(
        frame(), [detection(65)], moment=datetime(2026, 10, 20, 12, 0, 1, tzinfo=UTC)
    )

    passages = [event for event in events if event.event_type is EventType.PASSAGE]
    assert len(passages) == 1
    assert passages[0].direction is Direction.IN
    assert session.in_count == 1


def test_crossing_outside_schedule_triggers_siren(tmp_path) -> None:
    siren = SimulatedSiren()
    service = MonitorService(EventStore(tmp_path / "events.sqlite3"), siren)
    service.start_session(1, time(8), time(16), 0)
    service.process_frame(frame(), [detection(35)], moment=datetime(2026, 10, 20, 20, tzinfo=UTC))
    events = service.process_frame(
        frame(), [detection(65)], moment=datetime(2026, 10, 20, 20, 0, 1, tzinfo=UTC)
    )

    assert [event.event_type for event in events] == [EventType.PASSAGE, EventType.AFTER_HOURS]
    assert siren.status()["active"] is True


def test_session_end_records_mismatch_and_can_be_acknowledged(tmp_path) -> None:
    store = EventStore(tmp_path / "events.sqlite3")
    siren = SimulatedSiren()
    service = MonitorService(store, siren)
    session = service.start_session(3, time(0), time(23, 59), 0)

    service.stop_session(datetime(2026, 10, 20, 12, tzinfo=UTC))
    events = store.list(session_id=session.session_id)
    alert = events[0]

    assert alert["event_type"] == EventType.COUNT_MISMATCH.value
    assert alert["details"]["difference"] == 3
    assert alert["acknowledged"] is False
    assert store.acknowledge(alert["event_id"]) is True
    assert store.list(session_id=session.session_id)[0]["acknowledged"] is True
    assert siren.status()["active"] is True


def test_outbox_keeps_event_until_transport_confirms(tmp_path) -> None:
    store = EventStore(tmp_path / "events.sqlite3")
    service = MonitorService(store)
    service.start_session(1, time(0), time(23, 59), 0)
    service.process_frame(frame(), [detection(35)])
    service.process_frame(frame(), [detection(65)])
    pending = store.pending()

    assert len(pending) == 1
    event_id = pending[0]["event_id"]
    store.mark_synced(event_id)
    assert store.pending() == []


def test_session_survives_service_restart(tmp_path) -> None:
    database = tmp_path / "events.sqlite3"
    first = MonitorService(EventStore(database))
    session = first.start_session(2, time(8), time(17), 1)
    first.process_frame(frame(), [detection(35)])
    first.process_frame(frame(), [detection(65)])

    restored = MonitorService(EventStore(database))

    assert restored.session is not None
    assert restored.session.session_id == session.session_id
    assert restored.session.in_count == 1
    assert restored.session.expected_passages == 2
    assert restored.session.time_zone == "America/Sao_Paulo"


def test_event_image_is_saved_and_retention_removes_old_files(tmp_path) -> None:
    evidence = EvidenceStore(tmp_path / "evidence", retention_days=2)
    service = MonitorService(EventStore(tmp_path / "events.sqlite3"), evidence_store=evidence)
    service.start_session(1, time(0), time(23, 59), 0)
    service.process_frame(frame(), [detection(35)])
    events = service.process_frame(frame(), [detection(65)])
    stored = service.store.list()

    evidence_ref = stored[0]["details"]["evidence_ref"]
    event_id = evidence_ref.rsplit("/", 1)[-1].removesuffix(".jpg")
    assert evidence.path_for(event_id) is not None
    assert len(events) == 1
    image_path = evidence.path_for(event_id)
    assert image_path is not None
    image_path.touch()
    import os

    os.utime(image_path, (1, 1))
    assert evidence.cleanup(now=3 * 86400) == 1


def test_evidence_failure_does_not_drop_passage(tmp_path) -> None:
    class UnavailableEvidence:
        def save(self, event_id: str, image: np.ndarray) -> str:
            raise OSError("disco indisponível")

    store = EventStore(tmp_path / "events.sqlite3")
    service = MonitorService(store, evidence_store=UnavailableEvidence())  # type: ignore[arg-type]
    session = service.start_session(1, time(0), time(23, 59), 0)
    service.process_frame(frame(), [detection(35)])
    events = service.process_frame(frame(), [detection(65)])

    assert len(events) == 1
    assert events[0].event_type is EventType.PASSAGE
    assert store.counts(session.session_id)["in"] == 1


def test_local_video_runs_through_detector_tracker_and_counter(tmp_path) -> None:
    video_path = tmp_path / "passage.avi"
    writer = cv2.VideoWriter(str(video_path), cv2.VideoWriter_fourcc(*"MJPG"), 10, (120, 80))
    assert writer.isOpened()
    for x in range(15, 106, 8):
        image = np.zeros((80, 120, 3), dtype=np.uint8)
        cv2.circle(image, (x, 40), 12, (0, 255, 0), -1)
        writer.write(image)
    writer.release()

    store = EventStore(tmp_path / "events.sqlite3")
    service = MonitorService(store)
    session = service.start_session(1, time(0), time(23, 59), 0)
    worker = VideoWorker(str(video_path), GreenMarkerDetector(), service)
    worker.start()
    deadline = monotonic() + 5
    while service.camera_state != "ended" and monotonic() < deadline:
        sleep(0.05)
    worker.stop()

    assert service.camera_state == "ended"
    assert service.session is not None
    assert service.session.in_count == 1
    assert store.counts(session.session_id)["passage"] == 1


def test_demo_dashboard_and_api_session_flow() -> None:
    from fazenda_cv.app import StartSessionRequest, dashboard, start_session, stop_session

    page = dashboard()
    assert "Monitoramento do corredor" in page.path.read_text()
    started = start_session(
        StartSessionRequest(
            expected_passages=2,
            allowed_from="00:00",
            allowed_until="23:59",
        )
    )
    assert started["session"]["active"] is True
    stopped = stop_session()
    assert stopped["session"]["active"] is False


def test_stop_requires_an_active_session(tmp_path) -> None:
    service = MonitorService(EventStore(tmp_path / "events.sqlite3"))
    try:
        service.stop_session()
    except ValueError as error:
        assert "Não existe sessão ativa" in str(error)
    else:
        raise AssertionError("Esperava falha ao encerrar sem sessão ativa")
