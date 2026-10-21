from __future__ import annotations

import re
import shutil
import subprocess
import time
from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Protocol

import cv2
import numpy as np


@dataclass(frozen=True, slots=True)
class CapturedFrame:
    image: np.ndarray
    occurred_at: datetime


class FrameSource(Protocol):
    def frames(self) -> Iterator[CapturedFrame]: ...


class OpenCVSource:
    """Reads a video file or RTSP stream without changing downstream CV code."""

    def __init__(self, location: str, reconnect_seconds: float = 2) -> None:
        self.location = location
        self.reconnect_seconds = reconnect_seconds

    def frames(self) -> Iterator[CapturedFrame]:
        rtsp = self.location.lower().startswith(("rtsp://", "rtsps://"))
        while True:
            capture = cv2.VideoCapture()
            if rtsp:
                capture.open(
                    self.location,
                    cv2.CAP_FFMPEG,
                    [
                        cv2.CAP_PROP_OPEN_TIMEOUT_MSEC,
                        5000,
                        cv2.CAP_PROP_READ_TIMEOUT_MSEC,
                        5000,
                    ],
                )
            else:
                capture.open(self.location, cv2.CAP_FFMPEG)
            if not capture.isOpened():
                capture.release()
                if rtsp:
                    time.sleep(self.reconnect_seconds)
                    continue
                raise OSError(f"Não foi possível abrir o vídeo: {self.location}")
            try:
                fps = capture.get(cv2.CAP_PROP_FPS)
                started_at = datetime.now(UTC)
                frame_index = 0
                while True:
                    ok, frame = capture.read()
                    if not ok:
                        break
                    moment = (
                        datetime.now(UTC)
                        if rtsp or not fps or fps <= 0
                        else started_at + timedelta(seconds=frame_index / fps)
                    )
                    yield CapturedFrame(frame, moment)
                    frame_index += 1
            finally:
                capture.release()
            if not rtsp:
                return
            time.sleep(self.reconnect_seconds)


class X11WindowSource:
    """Captures only the X11 window selected by id, through FFmpeg."""

    def __init__(self, window_id: str, width: int = 960, height: int = 540, fps: int = 10) -> None:
        if shutil.which("ffmpeg") is None:
            raise RuntimeError("FFmpeg é necessário para capturar uma janela X11")
        if not re.fullmatch(r"0x[0-9a-fA-F]+", window_id):
            raise ValueError("window_id deve ser um identificador X11 hexadecimal")
        self.window_id = window_id
        self.width = width
        self.height = height
        self.fps = fps

    def frames(self) -> Iterator[CapturedFrame]:
        import os

        display = os.environ.get("DISPLAY")
        if not display:
            raise RuntimeError("DISPLAY indisponível; abra o Godot em uma sessão X11/XWayland")
        process = subprocess.Popen(
            [
                "ffmpeg",
                "-nostdin",
                "-loglevel",
                "error",
                "-f",
                "x11grab",
                "-draw_mouse",
                "0",
                "-window_id",
                self.window_id,
                "-framerate",
                str(self.fps),
                "-i",
                display,
                "-vf",
                f"scale={self.width}:{self.height}",
                "-pix_fmt",
                "bgr24",
                "-f",
                "rawvideo",
                "pipe:1",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        assert process.stdout is not None
        frame_bytes = self.width * self.height * 3
        try:
            while True:
                raw = bytearray()
                while len(raw) < frame_bytes:
                    chunk = process.stdout.read(frame_bytes - len(raw))
                    if not chunk:
                        if raw:
                            raise OSError("Captura da janela terminou no meio de um quadro")
                        raise OSError(
                            "Captura da janela encerrada. Verifique se o Godot continua "
                            "visível e se o X11 permite capturá-lo."
                        )
                    raw.extend(chunk)
                image = (
                    np.frombuffer(raw, dtype=np.uint8).reshape(self.height, self.width, 3).copy()
                )
                yield CapturedFrame(image, datetime.now(UTC))
        finally:
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
            process.stdout.close()


def find_x11_window(
    *, pid: int | None = None, title: str | None = None, timeout: float = 10
) -> str:
    """Finds a Godot window by its process id or a title fragment."""
    if not pid and not title:
        raise ValueError("Informe pid ou title")
    if shutil.which("xprop") is None:
        raise RuntimeError("xprop é necessário para localizar a janela do Godot")
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        root = subprocess.run(
            ["xprop", "-root", "_NET_CLIENT_LIST"],
            capture_output=True,
            text=True,
            check=False,
            timeout=3,
        )
        for window_id in re.findall(r"0x[0-9a-fA-F]+", root.stdout):
            properties = subprocess.run(
                ["xprop", "-id", window_id, "_NET_WM_PID", "WM_NAME"],
                capture_output=True,
                text=True,
                check=False,
                timeout=3,
            )
            pid_match = re.search(r"_NET_WM_PID\(CARDINAL\) = (\d+)", properties.stdout)
            if pid is not None and pid_match and int(pid_match.group(1)) == pid:
                return window_id
            if title is not None and title.lower() in properties.stdout.lower():
                return window_id
        time.sleep(0.25)
    raise RuntimeError("Janela X11 do simulador não encontrada; confirme que o Godot está visível")


def launch_godot(executable: str) -> subprocess.Popen[bytes]:
    path = Path(executable).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(path)
    return subprocess.Popen(
        [str(path), "--display-driver", "x11", "--windowed", "--audio-driver", "Dummy"],
        cwd=path.parent,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
