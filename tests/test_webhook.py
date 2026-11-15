import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from fazenda_cv.webhook import EventOutbox


def test_retry_restart_and_deduplication(tmp_path):
    received = []
    statuses = [503, 200]

    class Receiver(BaseHTTPRequestHandler):
        def do_POST(self):
            received.append(
                (
                    json.loads(self.rfile.read(int(self.headers["Content-Length"]))),
                    self.headers["Idempotency-Key"],
                    self.headers["Authorization"],
                )
            )
            self.send_response(statuses.pop(0))
            self.end_headers()

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Receiver)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        path = tmp_path / "queue.db"
        payload = {"event_id": "one", "schema_version": 2, "event_type": "passage"}
        queue = EventOutbox(path)
        queue.enqueue(payload)
        queue.enqueue(payload)
        url = f"http://127.0.0.1:{server.server_port}/events"
        assert queue.deliver_once(url, now=0, token="test") == 0
        restarted = EventOutbox(path)
        assert restarted.deliver_once(url, now=1) == 0
        assert restarted.deliver_once(url, now=2, token="test") == 1
        assert restarted.deliver_once(url, now=100) == 0
        assert len(received) == 2
        assert received[0] == received[1] == (payload, "one", "Bearer test")
    finally:
        server.shutdown()
        server.server_close()
        worker.join()


def test_conflicting_payload_and_invalid_version(tmp_path):
    queue = EventOutbox(tmp_path / "queue.db")
    queue.enqueue({"event_id": "one", "schema_version": 2})
    with pytest.raises(ValueError, match="outro payload"):
        queue.enqueue({"event_id": "one", "schema_version": 2, "extra": True})
    with pytest.raises(ValueError):
        queue.enqueue({"event_id": "two", "schema_version": 1})
