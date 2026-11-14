"""API подготовки, повторного использования и передачи субтитров."""

import asyncio
import time
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException, Response, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from pydantic import BaseModel, HttpUrl

from api.services.caption_identity import cache_identity
from api.services.caption_jobs import get_job, start_job
from api.services.caption_repository import CaptionRepository

router = APIRouter(prefix="/captions", tags=["captions"])


class PrepareRequest(BaseModel):
    """Запрос подготовки транскрипта для страницы видео."""

    video_url: HttpUrl
    mode: Literal["local", "cloud"] = "local"
    translate_to: str = ""
    translation_engine: Literal["opus", "argos"] = "opus"


@router.post("/prepare")
async def prepare(request: PrepareRequest, response: Response) -> dict:
    """Проверяет URL UN Web TV и ставит подготовку субтитров в очередь."""
    url = str(request.video_url)
    parsed = urlparse(url)
    if parsed.hostname != "webtv.un.org" or "/asset/" not in parsed.path:
        raise HTTPException(status_code=400, detail="Поддерживаются только страницы видео UN Web TV")
    identity = cache_identity(
        url,
        request.mode,
        request.translate_to,
        request.translation_engine,
    )
    repository = CaptionRepository()
    cached = repository.get_cues(identity["cache_key"])
    media = repository.get_media(identity["asset_key"])
    if cached and cached["is_complete"] and media and Path(media["audio_path"]).is_file():
        return {
            "status": "complete",
            "cached": True,
            "asset_key": identity["asset_key"],
            "cues": cached["cues"],
        }
    response.status_code = 202
    return start_job(identity["canonical_url"], request.mode, identity)


@router.get("/jobs/{job_id}")
def read_job(job_id: str) -> dict:
    """Возвращает этап, прогресс и готовые фразы задачи."""
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Задача подготовки не найдена")
    if job["status"] == "complete":
        cached = CaptionRepository().get_cues(job["cache_key"])
        job["cues"] = cached["cues"] if cached else []
    return job


@router.websocket("/jobs/{job_id}/ws")
async def stream_job(websocket: WebSocket, job_id: str) -> None:
    """Передаёт изменения состояния задачи по WebSocket."""
    await websocket.accept()
    last_version = None
    last_sent = time.monotonic()
    try:
        while True:
            job = get_job(job_id)
            if not job:
                await websocket.send_json(
                    {"type": "failed", "message": "Задача подготовки не найдена"}
                )
                return
            payload_job = job
            if job["status"] == "complete":
                cached = CaptionRepository().get_cues(job["cache_key"])
                payload_job = {**job, "cues": cached["cues"] if cached else []}
            event_type = "update"
            if job["status"] == "partial":
                event_type = "partial"
            elif last_version is None and job.get("blocks_done", 0):
                event_type = "snapshot"
            payload = {"type": event_type, "job": payload_job}
            if job["version"] != last_version:
                await websocket.send_json(payload)
                last_version = job["version"]
                last_sent = time.monotonic()
            elif time.monotonic() - last_sent >= 15:
                await websocket.send_json({"type": "heartbeat"})
                last_sent = time.monotonic()
            if job["status"] in {"complete", "failed"}:
                return
            await asyncio.sleep(0.5)
    except (WebSocketDisconnect, RuntimeError):
        return


@router.get("/media/{asset_key}")
def get_media(asset_key: str) -> FileResponse:
    """Отдаёт сохранённый FLAC-архив для указанной записи."""
    if len(asset_key) != 64 or any(char not in "0123456789abcdef" for char in asset_key):
        raise HTTPException(status_code=400, detail="Некорректный ключ аудиоархива")
    media = CaptionRepository().get_media(asset_key)
    if not media:
        raise HTTPException(status_code=404, detail="Аудиоархив не найден")
    path = media["audio_path"]
    if not Path(path).is_file():
        raise HTTPException(status_code=404, detail="Файл FLAC отсутствует на диске")
    return FileResponse(path, media_type="audio/flac", filename=f"{asset_key}.flac")
