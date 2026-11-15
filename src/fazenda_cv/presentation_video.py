"""Export interpolated presentation copies without changing analysis events."""

from __future__ import annotations

import argparse
import shutil
import subprocess
from math import isfinite
from pathlib import Path

import cv2


def export_presentation(source: Path, target: Path, *, fps: int = 30, width: int = 960) -> None:
    if fps not in {30, 60} or width < 64 or width % 2:
        raise ValueError("Use FPS 30/60 e largura par >= 64")
    if source.resolve() == target.resolve() or target.exists():
        raise ValueError("Informe uma saída nova para preservar os arquivos existentes")
    if not shutil.which("ffmpeg"):
        raise RuntimeError("FFmpeg é necessário")
    capture = cv2.VideoCapture(str(source))
    try:
        source_fps = capture.get(cv2.CAP_PROP_FPS)
        count = capture.get(cv2.CAP_PROP_FRAME_COUNT)
        if not capture.isOpened() or not isfinite(source_fps) or source_fps <= 0 or count < 3:
            raise ValueError("Vídeo exige FPS válido e pelo menos três quadros")
        duration = count / source_fps
    finally:
        capture.release()
    target.parent.mkdir(parents=True, exist_ok=True)
    filters = (
        f"scale={width}:-2,tpad=stop_mode=clone:stop_duration=2,"
        f"minterpolate=fps={fps}:mi_mode=mci:mc_mode=aobmc:me_mode=bidir,"
        f"trim=duration={duration},setpts=PTS-STARTPTS,"
        "drawtext=text='APRESENTACAO INTERPOLADA - deteccoes originais':"
        "x=10:y=h-28:fontsize=16:fontcolor=white:box=1:boxcolor=black@0.7"
    )
    subprocess.run(
        [
            "ffmpeg",
            "-nostdin",
            "-v",
            "error",
            "-n",
            "-i",
            str(source),
            "-vf",
            filters,
            "-an",
            "-c:v",
            "libopenh264",
            "-b:v",
            "3M",
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+faststart",
            str(target),
        ],
        check=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("target", type=Path)
    parser.add_argument("--fps", type=int, choices=[30, 60], default=30)
    parser.add_argument("--width", type=int, default=960)
    args = parser.parse_args()
    export_presentation(args.source, args.target, fps=args.fps, width=args.width)


if __name__ == "__main__":
    main()
