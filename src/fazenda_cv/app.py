from __future__ import annotations

import hmac
import logging
import os
from contextlib import asynccontextmanager
from datetime import time
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.responses import FileResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel, Field

from fazenda_cv.detection import GreenMarkerDetector, YoloXOnnxDetector
from fazenda_cv.domain import CountLine
from fazenda_cv.evidence import EvidenceStore
from fazenda_cv.service import MonitorService
from fazenda_cv.storage import EventStore
from fazenda_cv.video import OutboxWorker, SyntheticDemoWorker, VideoWorker

logging.basicConfig(level=os.getenv("FARM_CV_LOG_LEVEL", "INFO"))
logger = logging.getLogger(__name__)

HOST = os.getenv("FARM_CV_HOST", "127.0.0.1")
PORT = int(os.getenv("FARM_CV_PORT", "8000"))
DB_PATH = os.getenv("FARM_CV_DATABASE", "./data/fazenda-cv.sqlite3")
DATA_DIR = os.getenv("FARM_CV_DATA_DIR", "./data")
SOURCE = os.getenv("FARM_CV_CAMERA_SOURCE", "")
MODEL = os.getenv("FARM_CV_MODEL", "")
DEMO = os.getenv("FARM_CV_DEMO", "0") == "1"
USERNAME = os.getenv("FARM_CV_USERNAME", "")
PASSWORD = os.getenv("FARM_CV_PASSWORD", "")
ERP_URL = os.getenv("FARM_CV_ERP_EVENTS_URL", "")
ERP_TOKEN = os.getenv("FARM_CV_ERP_TOKEN", "")
TLS_CERT = os.getenv("FARM_CV_TLS_CERT", "")
TLS_KEY = os.getenv("FARM_CV_TLS_KEY", "")
COUNT_LINE = CountLine(
    start=(
        float(os.getenv("FARM_CV_LINE_START_X", "0.5")),
        float(os.getenv("FARM_CV_LINE_START_Y", "1.0")),
    ),
    end=(
        float(os.getenv("FARM_CV_LINE_END_X", "0.5")),
        float(os.getenv("FARM_CV_LINE_END_Y", "0.0")),
    ),
)

security = HTTPBasic(auto_error=False)
store = EventStore(DB_PATH)
service = MonitorService(
    store,
    farm_id=os.getenv("FARM_CV_FARM_ID", "fazenda-local"),
    camera_id=os.getenv("FARM_CV_CAMERA_ID", "camera-1"),
    time_zone=os.getenv("FARM_CV_TIMEZONE", "America/Sao_Paulo"),
    count_line=COUNT_LINE,
    evidence_store=EvidenceStore(
        Path(DATA_DIR) / "evidence",
        int(os.getenv("FARM_CV_EVIDENCE_RETENTION_DAYS", "7")),
    ),
)
video_worker: VideoWorker | None = None
demo_worker: SyntheticDemoWorker | None = None
outbox_worker: OutboxWorker | None = None


class StartSessionRequest(BaseModel):
    expected_passages: int = Field(ge=0, le=100_000)
    allowed_from: str = "00:00"
    allowed_until: str = "23:59"
    tolerance: int = Field(default=0, ge=0, le=1000)


def _parse_time(value: str) -> time:
    try:
        return time.fromisoformat(value)
    except ValueError as error:
        raise HTTPException(status_code=422, detail=f"Horário inválido: {value}") from error


def require_user(
    credentials: Annotated[HTTPBasicCredentials | None, Depends(security)],
) -> str:
    if not USERNAME and not PASSWORD:
        return "local"
    if not credentials or not (
        hmac.compare_digest(credentials.username, USERNAME)
        and hmac.compare_digest(credentials.password, PASSWORD)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciais inválidas",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username


@asynccontextmanager
async def lifespan(_: FastAPI):
    global video_worker, demo_worker, outbox_worker
    if HOST not in {"127.0.0.1", "localhost", "::1"}:
        if not USERNAME or not PASSWORD:
            raise RuntimeError("Acesso pela rede exige FARM_CV_USERNAME e FARM_CV_PASSWORD")
        if not TLS_CERT or not TLS_KEY:
            raise RuntimeError("Acesso pela rede exige FARM_CV_TLS_CERT e FARM_CV_TLS_KEY")
    if ERP_URL and (not ERP_URL.startswith("https://") or not ERP_TOKEN):
        raise RuntimeError("Sincronização ERP exige URL HTTPS e FARM_CV_ERP_TOKEN")
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

    try:
        ZoneInfo(service.time_zone)
    except ZoneInfoNotFoundError as error:
        raise RuntimeError("FARM_CV_TIMEZONE deve ser um identificador IANA válido") from error
    detector = None
    if DEMO:
        detector = GreenMarkerDetector()
    elif MODEL:
        if not Path(MODEL).is_file():
            raise RuntimeError("Arquivo do modelo informado não existe")
        detector = YoloXOnnxDetector(
            MODEL,
            class_id=int(os.getenv("FARM_CV_CATTLE_CLASS_ID", "19")),
        )
    if SOURCE:
        if detector is None:
            service.camera_state = "model_required"
            logger.warning("Fonte de vídeo configurada sem modelo; câmera não será processada")
        else:
            video_worker = VideoWorker(SOURCE, detector, service)
            video_worker.start()
    elif DEMO and detector:
        demo_worker = SyntheticDemoWorker(detector, service)
        demo_worker.start()
    if ERP_URL:
        outbox_worker = OutboxWorker(service, ERP_URL, ERP_TOKEN)
        outbox_worker.start()
    yield
    if video_worker:
        video_worker.stop()
    if demo_worker:
        demo_worker.stop()
    if outbox_worker:
        outbox_worker.stop()


app = FastAPI(title="Fazenda Digital CV", version="0.1.0", lifespan=lifespan)


@app.get("/", dependencies=[Depends(require_user)], include_in_schema=False)
def dashboard() -> str:
    return FileResponse(Path(__file__).parent / "static" / "index.html")


@app.get("/api/health", dependencies=[Depends(require_user)])
def health() -> dict[str, str]:
    return {"status": "ok", "version": "0.1.0"}


@app.get("/api/status", dependencies=[Depends(require_user)])
def get_status() -> dict[str, object]:
    return service.status()


@app.post("/api/sessions", dependencies=[Depends(require_user)])
def start_session(request: StartSessionRequest) -> dict[str, object]:
    try:
        service.start_session(
            request.expected_passages,
            _parse_time(request.allowed_from),
            _parse_time(request.allowed_until),
            request.tolerance,
        )
        return service.status()
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.post("/api/sessions/stop", dependencies=[Depends(require_user)])
def stop_session() -> dict[str, object]:
    try:
        session = service.stop_session()
        return {"session_id": session.session_id, **service.status()}
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@app.get("/api/events", dependencies=[Depends(require_user)])
def get_events(limit: int = 100, session_id: str | None = None) -> list[dict[str, object]]:
    return store.list(limit, session_id)


@app.get("/api/evidence/{event_id}", dependencies=[Depends(require_user)])
def get_evidence(event_id: str) -> FileResponse:
    evidence = service.evidence_store.path_for(event_id) if service.evidence_store else None
    if evidence is None:
        raise HTTPException(status_code=404, detail="Evidência não encontrada")
    return FileResponse(evidence, media_type="image/jpeg")


@app.post("/api/events/{event_id}/ack", dependencies=[Depends(require_user)])
def acknowledge_event(event_id: str) -> dict[str, bool]:
    found = store.acknowledge(event_id)
    if not found:
        raise HTTPException(status_code=404, detail="Evento não encontrado")
    return {"acknowledged": True}


@app.post("/api/siren/silence", dependencies=[Depends(require_user)])
def silence_siren() -> dict[str, object]:
    service.siren.silence()
    return service.status()["siren"]  # type: ignore[return-value]
