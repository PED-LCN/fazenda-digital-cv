from __future__ import annotations

import time
from pathlib import Path
from uuid import UUID

import cv2
import numpy as np


class EvidenceStore:
    """Keeps event-only JPEG evidence and removes files past the local retention period."""

    def __init__(self, directory: str | Path, retention_days: int = 7) -> None:
        self.directory = Path(directory)
        self.retention_days = max(0, retention_days)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.cleanup()

    def cleanup(self, now: float | None = None) -> int:
        if self.retention_days == 0:
            cutoff = now if now is not None else time.time()
        else:
            cutoff = (now if now is not None else time.time()) - self.retention_days * 86400
        removed = 0
        for path in self.directory.glob("*.jpg"):
            if path.stat().st_mtime < cutoff:
                path.unlink(missing_ok=True)
                removed += 1
        return removed

    def save(self, event_id: str, frame: np.ndarray) -> str | None:
        if self.retention_days == 0:
            return None
        identifier = str(UUID(event_id))
        success, encoded = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 82])
        if not success:
            raise OSError("Não foi possível codificar a evidência do evento")
        destination = self.directory / f"{identifier}.jpg"
        temporary = destination.with_suffix(".jpg.tmp")
        temporary.write_bytes(encoded.tobytes())
        temporary.replace(destination)
        return identifier

    def path_for(self, event_id: str) -> Path | None:
        try:
            identifier = str(UUID(event_id))
        except ValueError:
            return None
        path = self.directory / f"{identifier}.jpg"
        return path if path.is_file() else None
