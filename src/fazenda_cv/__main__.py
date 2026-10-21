from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

import cv2

from fazenda_cv.detection import SimulatorCowDetector, YoloXOnnxDetector
from fazenda_cv.domain import CountLine
from fazenda_cv.pipeline import CvPipeline
from fazenda_cv.sources import (
    FrameSource,
    OpenCVSource,
    X11WindowSource,
    find_x11_window,
    launch_godot,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Ferramenta local de visão computacional da Fazenda Digital"
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--source", help="Arquivo de vídeo ou URL RTSP")
    source.add_argument("--godot", help="Abre e monitora o executável Godot fornecido")
    source.add_argument("--window-id", help="ID hexadecimal de uma janela X11 já aberta")
    source.add_argument("--window-title", help="Parte do título de uma janela X11 já aberta")
    detector = parser.add_mutually_exclusive_group(required=True)
    detector.add_argument("--simulator", action="store_true", help="Detecta vacas cinzas do Godot")
    detector.add_argument("--model", help="Modelo bovino YOLOX em ONNX para vídeo real")
    parser.add_argument("--source-id", default="corredor-1")
    parser.add_argument(
        "--line",
        nargs=4,
        type=float,
        default=None,
        metavar=("X1", "Y1", "X2", "Y2"),
        help="Linha normalizada; esquerda->direita é entrada",
    )
    parser.add_argument(
        "--roi",
        nargs=4,
        type=float,
        default=(0.05, 0.12, 0.98, 0.95),
        metavar=("LEFT", "TOP", "RIGHT", "BOTTOM"),
    )
    parser.add_argument("--class-id", type=int, default=19, help="Classe bovino no modelo ONNX")
    parser.add_argument("--input-size", type=int, default=416)
    parser.add_argument("--fps", type=int, default=10, help="FPS da captura de janela")
    parser.add_argument(
        "--width", type=int, default=960, help="Largura processada na captura de janela"
    )
    parser.add_argument(
        "--height", type=int, default=540, help="Altura processada na captura de janela"
    )
    parser.add_argument(
        "--max-width",
        type=int,
        default=960,
        help="Reduz arquivos/câmera para esta largura; 0 mantém a resolução original",
    )
    parser.add_argument("--events", type=Path, help="Grava eventos JSONL, além de emitir no stdout")
    parser.add_argument(
        "--annotated", type=Path, help="Grava vídeo local com linha, caixas e contagens"
    )
    parser.add_argument(
        "--preview", action="store_true", help="Mostra vídeo anotado no ffplay se disponível"
    )
    parser.add_argument(
        "--max-frames", type=int, default=0, help="Limita quadros para demonstração/teste"
    )
    return parser


def _open_writer(path: Path, width: int, height: int, fps: int) -> cv2.VideoWriter:
    path.parent.mkdir(parents=True, exist_ok=True)
    codec = "MJPG" if path.suffix.lower() == ".avi" else "mp4v"
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*codec), fps, (width, height))
    if not writer.isOpened():
        raise OSError(f"Não foi possível criar vídeo anotado: {path}")
    return writer


def _open_preview(width: int, height: int, fps: int) -> subprocess.Popen[bytes]:
    if shutil.which("ffplay") is None:
        raise RuntimeError("ffplay não foi encontrado para a prévia")
    return subprocess.Popen(
        [
            "ffplay",
            "-loglevel",
            "error",
            "-f",
            "rawvideo",
            "-pixel_format",
            "bgr24",
            "-video_size",
            f"{width}x{height}",
            "-framerate",
            str(fps),
            "-i",
            "pipe:0",
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.fps < 1 or args.width < 16 or args.height < 16 or args.max_width < 0:
        parser.error("fps, largura e altura devem ser positivos")
    if args.max_frames < 0:
        parser.error("max-frames não pode ser negativo")
    if args.simulator and args.source and args.source.lower().startswith(("rtsp://", "rtsps://")):
        parser.error("Use um modelo ONNX para câmera real; --simulator exige cena fixa Godot")
    if args.model and not Path(args.model).is_file():
        parser.error("O modelo ONNX informado não existe")

    coordinates = args.line or ((0.38, 1, 0.38, 0) if args.simulator else (0.5, 1, 0.5, 0))
    line = CountLine((coordinates[0], coordinates[1]), (coordinates[2], coordinates[3]))
    detector = (
        SimulatorCowDetector(tuple(args.roi))
        if args.simulator
        else YoloXOnnxDetector(args.model, args.input_size, args.class_id)
    )
    pipeline = CvPipeline(detector, args.source_id, line)
    game: subprocess.Popen[bytes] | None = None
    writer: cv2.VideoWriter | None = None
    preview: subprocess.Popen[bytes] | None = None
    event_file = None
    frame_stream = None
    frames = 0
    started = time.monotonic()
    try:
        source: FrameSource
        if args.godot:
            game = launch_godot(args.godot)
            window_id = find_x11_window(pid=game.pid)
            source = X11WindowSource(window_id, args.width, args.height, args.fps)
        elif args.window_title:
            window_id = find_x11_window(title=args.window_title)
            source = X11WindowSource(window_id, args.width, args.height, args.fps)
        elif args.window_id:
            source = X11WindowSource(args.window_id, args.width, args.height, args.fps)
        else:
            source = OpenCVSource(args.source)
        if args.events:
            args.events.parent.mkdir(parents=True, exist_ok=True)
            event_file = args.events.open("a", encoding="utf-8")
        if args.simulator:
            print("Captura iniciada; crie vacas no Godot.", file=sys.stderr)
        frame_stream = source.frames()
        for sample in frame_stream:
            frame = sample.image
            if args.max_width and frame.shape[1] > args.max_width:
                new_height = round(frame.shape[0] * args.max_width / frame.shape[1])
                frame = cv2.resize(frame, (args.max_width, new_height))
            result = pipeline.process(frame, sample.occurred_at)
            frames += 1
            for event in result.events:
                payload = json.dumps(event.to_dict(), ensure_ascii=False, separators=(",", ":"))
                print(payload, flush=True)
                if event_file:
                    event_file.write(payload + "\n")
                    event_file.flush()
            if args.annotated or args.preview:
                image = pipeline.annotate(frame, result)
                height, width = image.shape[:2]
                if args.annotated:
                    if writer is None:
                        writer = _open_writer(args.annotated, width, height, args.fps)
                    writer.write(image)
                if args.preview:
                    if preview is None:
                        preview = _open_preview(width, height, args.fps)
                    try:
                        assert preview.stdin is not None
                        preview.stdin.write(image.tobytes())
                    except BrokenPipeError:
                        print("A prévia foi fechada; o processamento continuará.", file=sys.stderr)
                        args.preview = False
            if frames % max(1, args.fps * 3) == 0:
                elapsed = max(time.monotonic() - started, 0.001)
                print(
                    f"Quadros: {frames} | objetos: {len(result.detections)} | "
                    f"entradas: {result.in_count} | saídas: {result.out_count} | "
                    f"processamento: {frames / elapsed:.1f} fps",
                    file=sys.stderr,
                    flush=True,
                )
            if args.max_frames and frames >= args.max_frames:
                break
    except KeyboardInterrupt:
        pass
    except (OSError, RuntimeError, ValueError) as error:
        print(f"Erro: {error}", file=sys.stderr)
        return 2
    finally:
        if frame_stream is not None:
            frame_stream.close()
        if writer:
            writer.release()
        if preview:
            if preview.stdin:
                preview.stdin.close()
            preview.terminate()
            try:
                preview.wait(timeout=2)
            except subprocess.TimeoutExpired:
                preview.kill()
        if event_file:
            event_file.close()
        if game:
            game.terminate()
            try:
                game.wait(timeout=3)
            except subprocess.TimeoutExpired:
                game.kill()
    print(
        f"Concluído: {frames} quadros; {pipeline.counter.in_count} entradas; "
        f"{pipeline.counter.out_count} saídas.",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
