from __future__ import annotations

import logging
import threading

import cv2

from fazenda_cv.detection import Detector
from fazenda_cv.service import MonitorService

logger = logging.getLogger(__name__)


class VideoWorker:
    def __init__(self, source: str, detector: Detector, service: MonitorService) -> None:
        self.source = source
        self.detector = detector
        self.service = service
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="camera-reader", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=3)

    def _open(self) -> cv2.VideoCapture:
        capture = cv2.VideoCapture()
        if self.source.lower().startswith(("rtsp://", "rtsps://")):
            capture.open(
                self.source,
                cv2.CAP_FFMPEG,
                [
                    cv2.CAP_PROP_OPEN_TIMEOUT_MSEC,
                    5000,
                    cv2.CAP_PROP_READ_TIMEOUT_MSEC,
                    5000,
                ],
            )
        else:
            capture.open(self.source, cv2.CAP_FFMPEG)
        return capture

    def _run(self) -> None:
        is_stream = self.source.lower().startswith(("rtsp://", "rtsps://"))
        while not self._stop.is_set():
            capture = self._open()
            if not capture.isOpened():
                self.service.camera_state = "disconnected"
                capture.release()
                if is_stream:
                    self._stop.wait(3)
                    continue
                break
            self.service.camera_state = "streaming"
            fps = capture.get(cv2.CAP_PROP_FPS)
            frame_delay = 1 / fps if fps and 1 <= fps <= 120 and not is_stream else 0
            read_failed = False
            while not self._stop.is_set():
                ok, frame = capture.read()
                if not ok:
                    read_failed = True
                    break
                try:
                    detections = self.detector.detect(frame)
                    self.service.process_frame(
                        frame,
                        detections,
                        model_version=self.detector.model_version,
                    )
                except Exception:
                    logger.exception("Falha ao processar quadro; captura será retomada")
                    self.service.camera_state = "processing_error"
                if frame_delay:
                    self._stop.wait(frame_delay)
            capture.release()
            if not is_stream:
                self.service.camera_state = "ended" if read_failed else "idle"
                break
            self.service.camera_state = "reconnecting"
            self._stop.wait(2)
        if self._stop.is_set() and self.service.camera_state == "streaming":
            self.service.camera_state = "idle"


class SyntheticDemoWorker:
    """Generates a moving marker to exercise the complete pipeline without a camera."""

    def __init__(self, detector: Detector, service: MonitorService) -> None:
        self.detector = detector
        self.service = service
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, name="synthetic-demo", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=3)

    def _run(self) -> None:
        import numpy as np

        width, height = 640, 360
        position = 0
        direction = 1
        while not self._stop.is_set():
            frame = np.zeros((height, width, 3), dtype=np.uint8)
            line = self.service.count_line
            start = (int(line.start[0] * width), int(line.start[1] * height))
            end = (int(line.end[0] * width), int(line.end[1] * height))
            cv2.line(frame, start, end, (90, 90, 90), 2)
            cv2.ellipse(frame, (position, height // 2), (28, 40), 0, 0, 360, (0, 255, 0), -1)
            self.service.process_frame(
                frame,
                self.detector.detect(frame),
                model_version=self.detector.model_version,
            )
            self.service.camera_state = "demo"
            position += 4 * direction
            if position >= width - 30 or position <= 30:
                direction *= -1
            self._stop.wait(0.05)


class OutboxWorker:
    def __init__(self, service: MonitorService, url: str, token: str, interval: float = 10) -> None:
        self.service = service
        self.url = url
        self.token = token
        self.interval = interval
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, name="event-outbox", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=3)

    def _run(self) -> None:
        import json
        from urllib.error import URLError
        from urllib.request import Request, urlopen

        from fazenda_cv.storage import EventStore

        store: EventStore = self.service.store
        while not self._stop.is_set():
            for payload in store.pending():
                event_id = str(payload["event_id"])
                request = Request(
                    self.url,
                    data=json.dumps(payload).encode(),
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {self.token}",
                        "Idempotency-Key": event_id,
                    },
                    method="POST",
                )
                try:
                    with urlopen(request, timeout=5) as response:
                        if 200 <= response.status < 300:
                            store.mark_synced(event_id)
                except URLError:
                    break
            self._stop.wait(self.interval)
