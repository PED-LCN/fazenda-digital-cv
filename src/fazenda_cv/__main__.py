from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from collections.abc import Iterator
from math import isfinite
from pathlib import Path
from uuid import uuid4

import cv2
import numpy as np

from fazenda_cv.areas import annotate_areas, load_areas
from fazenda_cv.detection import SimulatorCowDetector, YoloXOnnxDetector
from fazenda_cv.domain import CountLine
from fazenda_cv.integration_events import passage_to_integration_event
from fazenda_cv.model_qualification import load_model_card
from fazenda_cv.occupancy import measure_occupancy
from fazenda_cv.pipeline import CvPipeline
from fazenda_cv.run_report import RunReport
from fazenda_cv.sources import (
    FrameSource,
    OpenCVSource,
    X11WindowSource,
    find_x11_window,
    launch_godot,
)
from fazenda_cv.tiled_detection import TiledDetector
from fazenda_cv.webhook import EventOutbox


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
    detector.add_argument("--model-card", type=Path, help="Cartão TOML verificado do modelo YOLOX")
    parser.add_argument("--source-id", default="corredor-1")
    parser.add_argument("--areas-config", type=Path)
    parser.add_argument("--occupancy-events", type=Path)
    parser.add_argument("--start-seconds", type=float, default=0)
    parser.add_argument("--duration-seconds", type=float)
    parser.add_argument("--frame-step", type=int, default=1)
    parser.add_argument("--outbox", type=Path, help="Fila persistente de eventos v2")
    parser.add_argument("--access-id", help="Acesso atribuído à linha de passagem")
    parser.add_argument(
        "--detection-only", action="store_true", help="Detecta e anota sem emitir passagens"
    )
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
    parser.add_argument("--cpu-threads", type=int, default=4)
    parser.add_argument(
        "--confidence-threshold",
        type=float,
        default=0.35,
        help="Confiança mínima da detecção ONNX (padrão: 0.35)",
    )
    parser.add_argument(
        "--tile-size", type=int, default=0, help="Lado dos recortes em pixels; 0 desativa"
    )
    parser.add_argument(
        "--tile-overlap", type=int, default=0, help="Sobreposição entre recortes em pixels"
    )
    parser.add_argument(
        "--fps", type=int, default=30, help="FPS solicitado na captura de janela (padrão: 30)"
    )
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
    parser.add_argument("--run-report", type=Path, help="Resumo operacional JSON da execução")
    parser.add_argument(
        "--annotated", type=Path, help="Grava vídeo local com linha, caixas e contagens"
    )
    parser.add_argument(
        "--preview", action="store_true", help="Mostra vídeo anotado no ffplay se disponível"
    )
    parser.add_argument(
        "--draw-line",
        action="store_true",
        help="Desenha a linha no primeiro quadro com o mouse (requer OpenCV com GUI)",
    )
    parser.add_argument(
        "--max-frames", type=int, default=0, help="Limita quadros para demonstração/teste"
    )
    return parser


def _open_writer(path: Path, width: int, height: int, fps: float) -> cv2.VideoWriter:
    path.parent.mkdir(parents=True, exist_ok=True)
    codec = "MJPG" if path.suffix.lower() == ".avi" else "mp4v"
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*codec), fps, (width, height))
    if not writer.isOpened():
        raise OSError(f"Não foi possível criar vídeo anotado: {path}")
    return writer


def _open_preview(width: int, height: int, fps: float) -> subprocess.Popen[bytes]:
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


def _draw_line(frame: np.ndarray, samples: Iterator) -> tuple[CountLine, np.ndarray]:
    if "GUI:                           NONE" in cv2.getBuildInformation():
        raise RuntimeError("--draw-line requer OpenCV com GUI; instale opencv-python no ambiente")
    window = "Fazenda CV - arraste a linha; Enter confirma; Esc cancela"
    points: list[tuple[int, int]] = []
    dragging = False
    display_size = (frame.shape[1], frame.shape[0])

    def mouse(event: int, x: int, y: int, _flags: int, _param: object) -> None:
        nonlocal dragging
        if event == cv2.EVENT_LBUTTONDOWN:
            points[:] = [(x, y), (x, y)]
            dragging = True
        elif event == cv2.EVENT_MOUSEMOVE and dragging:
            points[1] = (x, y)
        elif event == cv2.EVENT_LBUTTONUP and dragging:
            points[1] = (x, y)
            dragging = False

    try:
        cv2.namedWindow(window, cv2.WINDOW_NORMAL)
        cv2.setMouseCallback(window, mouse)
        while True:
            sample = next(samples, None)
            if sample is None:
                raise RuntimeError("Fonte de vídeo encerrada durante o desenho da linha")
            frame = sample.image
            if (frame.shape[1], frame.shape[0]) != display_size:
                frame = cv2.resize(frame, display_size)
            image = frame.copy()
            if len(points) == 2:
                cv2.line(image, points[0], points[1], (0, 220, 255), 2)
            cv2.imshow(window, image)
            key = cv2.waitKey(30) & 0xFF
            if key in (10, 13) and len(points) == 2 and points[0] != points[1]:
                break
            if key == 27:
                raise RuntimeError("Desenho da linha cancelado")
    finally:
        cv2.destroyWindow(window)
    height, width = frame.shape[:2]
    line = CountLine(
        (points[0][0] / width, points[0][1] / height),
        (points[1][0] / width, points[1][1] / height),
    )
    return line, frame


def _gui_available() -> bool:
    return not any(
        line.strip().startswith("GUI:") and "NONE" in line
        for line in cv2.getBuildInformation().splitlines()
    )


def _output_fps(source: FrameSource, fallback_fps: int) -> float:
    if isinstance(source, OpenCVSource) and source.fps is not None:
        return source.fps / source.frame_step
    return fallback_fps


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.occupancy_events and not args.areas_config:
        parser.error("occupancy-events exige areas-config")
    if args.outbox and not args.access_id and not args.detection_only:
        parser.error("--outbox exige --access-id")
    if (
        not isfinite(args.start_seconds)
        or args.start_seconds < 0
        or args.frame_step < 1
        or (
            args.duration_seconds is not None
            and (not isfinite(args.duration_seconds) or args.duration_seconds <= 0)
        )
    ):
        parser.error("Trecho ou intervalo de quadros inválido")
    if (args.start_seconds or args.duration_seconds is not None or args.frame_step != 1) and (
        not args.source or args.source.lower().startswith(("rtsp://", "rtsps://"))
    ):
        parser.error("Seleção de trecho exige arquivo de vídeo")
    if args.draw_line and not _gui_available():
        parser.error("--draw-line requer OpenCV com GUI; instale opencv-python")
    if args.draw_line and args.detection_only:
        parser.error("--draw-line não se aplica ao modo --detection-only")
    if args.cpu_threads < 1:
        parser.error("cpu-threads deve ser positivo")
    if args.fps < 1 or args.width < 16 or args.height < 16 or args.max_width < 0:
        parser.error("fps, largura e altura devem ser positivos")
    if args.max_frames < 0:
        parser.error("max-frames não pode ser negativo")
    if not 0 < args.confidence_threshold <= 1:
        parser.error("confidence-threshold deve estar entre 0 (exclusivo) e 1")
    if args.simulator and args.confidence_threshold != 0.35:
        parser.error("--confidence-threshold exige um modelo ONNX")
    if (
        args.tile_size < 0
        or args.tile_overlap < 0
        or (args.tile_size == 0 and args.tile_overlap)
        or (args.tile_size and args.tile_overlap >= args.tile_size)
    ):
        parser.error("tile-size deve ser positivo e tile-overlap menor que tile-size")
    if args.tile_size and args.simulator:
        parser.error("--tile-size exige um modelo ONNX")
    if args.tile_size and args.max_width:
        parser.error("Use --max-width 0 com --tile-size para preservar a resolução")
    if args.simulator and args.source and args.source.lower().startswith(("rtsp://", "rtsps://")):
        parser.error("Use um modelo ONNX para câmera real; --simulator exige cena fixa Godot")
    if args.model and not Path(args.model).is_file():
        parser.error("O modelo ONNX informado não existe")
    if args.model_card:
        try:
            card = load_model_card(args.model_card)
        except (OSError, ValueError) as error:
            parser.error(f"Model card inválido: {error}")
        args.model = str(card.path)
        args.input_size = card.input_size
        args.class_id = card.cattle_class_id

    coordinates = args.line or ((0.34, 0.32, 0.34, 0.13) if args.simulator else (0.5, 1, 0.5, 0))
    line = CountLine((coordinates[0], coordinates[1]), (coordinates[2], coordinates[3]))
    detector = (
        SimulatorCowDetector(tuple(args.roi))
        if args.simulator
        else YoloXOnnxDetector(
            args.model,
            args.input_size,
            args.class_id,
            confidence_threshold=args.confidence_threshold,
            cpu_threads=args.cpu_threads,
        )
    )
    if args.tile_size:
        detector = TiledDetector(detector, args.tile_size, args.tile_overlap)
    area = None
    if args.areas_config:
        try:
            area = load_areas(args.areas_config)[args.source_id]
        except (OSError, ValueError, KeyError) as error:
            parser.error(f"Áreas inválidas: {error}")
    pipeline = CvPipeline(detector, args.source_id, line, count_passages=not args.detection_only)
    report = RunReport(args.source_id, detector.model_version)
    outbox = EventOutbox(args.outbox) if args.outbox else None
    live_session = str(uuid4())
    game: subprocess.Popen[bytes] | None = None
    writer: cv2.VideoWriter | None = None
    preview: subprocess.Popen[bytes] | None = None
    event_file = None
    occupancy_file = None
    frame_stream = None
    frames = 0
    started = time.monotonic()
    try:
        if args.occupancy_events:
            args.occupancy_events.parent.mkdir(parents=True, exist_ok=True)
            occupancy_file = args.occupancy_events.open("w", encoding="utf-8")
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
            source = OpenCVSource(
                args.source,
                start_seconds=args.start_seconds,
                duration_seconds=args.duration_seconds,
                frame_step=args.frame_step,
            )
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
            if args.draw_line:
                image = frame.copy()
                cv2.putText(
                    image,
                    "Pressione L para desenhar; Q para sair",
                    (12, 30),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (255, 255, 255),
                    2,
                )
                cv2.imshow("Fazenda CV - aguardando calibracao", image)
                key = cv2.waitKey(1) & 0xFF
                if key in (ord("q"), 27):
                    break
                if key != ord("l"):
                    continue
                cv2.destroyWindow("Fazenda CV - aguardando calibracao")
                line, frame = _draw_line(frame, frame_stream)
                pipeline = CvPipeline(
                    detector, args.source_id, line, count_passages=not args.detection_only
                )
                started = time.monotonic()
                print(
                    f"Linha escolhida: --line {line.start[0]:.4f} {line.start[1]:.4f} "
                    f"{line.end[0]:.4f} {line.end[1]:.4f}",
                    file=sys.stderr,
                )
                args.draw_line = False
            result = pipeline.process(
                frame,
                sample.occurred_at,
                session_id=sample.session_id,
                video_offset_ms=sample.video_offset_ms,
                time_basis=sample.time_basis,
            )
            if area and (occupancy_file or outbox):
                occupancy = measure_occupancy(
                    result.detections,
                    area,
                    (frame.shape[1], frame.shape[0]),
                    session_id=sample.session_id or live_session,
                    occurred_at=sample.occurred_at,
                    time_basis=sample.time_basis,
                    video_offset_ms=sample.video_offset_ms,
                )
                for measurement in occupancy:
                    payload_v2 = measurement.to_dict()
                    if occupancy_file:
                        occupancy_file.write(json.dumps(payload_v2) + "\n")
                        occupancy_file.flush()
                    if outbox:
                        outbox.enqueue(payload_v2)
            report.record_frame(len(result.detections), len(result.events))
            frames += 1
            for event in result.events:
                if outbox:
                    wrapped = passage_to_integration_event(
                        event, access_id=args.access_id, session_id=live_session
                    )
                    outbox.enqueue(wrapped.to_dict())
                payload = json.dumps(event.to_dict(), ensure_ascii=False, separators=(",", ":"))
                print(payload, flush=True)
                if event_file:
                    event_file.write(payload + "\n")
                    event_file.flush()
            if args.annotated or args.preview:
                image = pipeline.annotate(frame, result)
                if area:
                    image = annotate_areas(image, area)
                height, width = image.shape[:2]
                output_fps = _output_fps(source, args.fps)
                if args.annotated:
                    if writer is None:
                        writer = _open_writer(args.annotated, width, height, output_fps)
                    writer.write(image)
                if args.preview:
                    if preview is None:
                        preview = _open_preview(width, height, output_fps)
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
        if _gui_available():
            cv2.destroyAllWindows()
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
        if occupancy_file:
            occupancy_file.close()
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
    if args.run_report:
        report.save(
            args.run_report,
            max(time.monotonic() - started, 0.001),
            configuration={
                "start_seconds": args.start_seconds,
                "duration_seconds": args.duration_seconds,
                "frame_step": args.frame_step,
                "confidence_threshold": args.confidence_threshold,
                "cpu_threads": args.cpu_threads,
                "tile_size": args.tile_size,
                "tile_overlap": args.tile_overlap,
                "detection_only": args.detection_only,
            },
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
