from __future__ import annotations

import argparse
import os


def main() -> None:
    parser = argparse.ArgumentParser(description="Monitor local de passagens de bovinos")
    parser.add_argument("--source", help="Arquivo de vídeo ou URL RTSP")
    parser.add_argument("--model", help="Modelo YOLOX em ONNX")
    parser.add_argument("--demo", action="store_true", help="Usa marcadores verdes sintéticos")
    parser.add_argument("--database", help="Arquivo SQLite")
    parser.add_argument("--host", help="Endereço de escuta (padrão localhost)")
    parser.add_argument("--port", type=int, help="Porta HTTP")
    args = parser.parse_args()
    if args.source:
        os.environ["FARM_CV_CAMERA_SOURCE"] = args.source
    if args.model:
        os.environ["FARM_CV_MODEL"] = args.model
    if args.demo:
        os.environ["FARM_CV_DEMO"] = "1"
    if args.database:
        os.environ["FARM_CV_DATABASE"] = args.database
    if args.host:
        os.environ["FARM_CV_HOST"] = args.host
    if args.port:
        os.environ["FARM_CV_PORT"] = str(args.port)

    import uvicorn

    from fazenda_cv.app import HOST, PORT, TLS_CERT, TLS_KEY

    uvicorn.run(
        "fazenda_cv.app:app",
        host=HOST,
        port=PORT,
        ssl_certfile=TLS_CERT or None,
        ssl_keyfile=TLS_KEY or None,
    )


if __name__ == "__main__":
    main()
