# read.py — Эндпоинты чтения (GET)
from typing import Optional, List
from fastapi import APIRouter, Query, HTTPException
from database import Database
from ..models import VideoResponse, DownloadLogResponse
from parser import parse_video_page
from transcript_extractor import extract_transcript_from_url

router = APIRouter()


@router.get("/", response_model=List[VideoResponse])
async def list_videos(
    status: Optional[str] = Query(None, description="Фильтр по статусу"),
    limit: int = Query(50, ge=1, le=500, description="Лимит записей")
):
    """Список всех видео в базе."""
    db = Database()
    videos = db.get_videos(status=status, limit=limit)
    return [_build_video_response(v) for v in videos]


def _build_video_response(v) -> VideoResponse:
    """Вспомогательная функция сборки ответа."""
    return VideoResponse(
        id=v.id, title=v.title, url=v.un_video_url,
        date=v.date or v.source_date or "",
        description=v.description or "", category=v.category or "",
        thumbnail=v.thumbnail or "", tags=v.tags or "",
        duration=v.duration or "", status=v.status,
        source_date=v.source_date or "", local_video_path=v.local_video_path
    )


@router.get("/{video_id}", response_model=VideoResponse)
async def get_video(video_id: int):
    """Получить видео по ID."""
    db = Database()
    video = db.get_video(video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Видео не найдено")
    return _build_video_response(video)


@router.get("/{video_id}/logs", response_model=List[DownloadLogResponse])
async def get_video_logs(video_id: int):
    """Получить логи видео."""
    db = Database()
    if not db.get_video(video_id):
        raise HTTPException(status_code=404, detail="Видео не найдено")
    logs = db.get_download_logs(video_id)
    return [_build_log_response(log) for log in logs]


def _build_log_response(log) -> DownloadLogResponse:
    """Вспомогательная функция сборки лога."""
    return DownloadLogResponse(
        id=log.id, video_id=log.video_id, action=log.action,
        log_text=log.log_text, status=log.status,
        created_at=log.created_at or ""
    )


@router.get("/{video_id}/details")
async def get_video_details(video_id: int):
    """Получить детали видео (парсинг страницы UN)."""
    db = Database()
    video = db.get_video(video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Видео не найдено")
    details = parse_video_page(video.un_video_url)
    _update_video_from_details(db, video_id, details)
    return details


def _update_video_from_details(db, video_id: int, details: dict):
    """Обновление видео данными из парсинга."""
    db.update_video(
        video_id,
        description=details.get("description", ""),
        broadcasting_entity=details.get("broadcasting_entity", ""),
        languages=details.get("original_languages", ""),
        tags=details.get("categories", ""),
        duration=details.get("video_length", "")
    )


@router.get("/{video_id}/transcript")
async def get_transcript(video_id: int):
    """Получить транскрипт видео."""
    from ..services import transcript_service
    return await transcript_service.get_transcript(video_id)


@router.get("/{video_id}/segments-info")
async def get_segments_info(video_id: int):
    """Получить информацию о сегментах видео."""
    from ..services import video_service
    return await video_service.get_segments_info(video_id)
