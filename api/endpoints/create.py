# create.py — Эндпоинты создания (POST)
from fastapi import APIRouter, HTTPException
from database import Database, Video
from ..models import VideoCreate, VideoResponse

router = APIRouter()


@router.post("/", response_model=VideoResponse)
async def create_video(video: VideoCreate):
    """Добавить новое видео."""
    db = Database()
    video_data = _build_video_entity(video)
    video_id = db.add_video(video_data)
    if not video_id:
        raise HTTPException(status_code=500, detail="Не удалось создать видео")
    return _build_create_response(video_id, video)


def _build_video_entity(video: VideoCreate) -> Video:
    """Сборка объекта Video из модели создания."""
    return Video(
        un_video_url=video.url, title=video.title,
        source_date=video.source_date or "", description=video.description or "",
        category=video.category or "", thumbnail=video.thumbnail or "",
        tags=video.tags or "", broadcasting_entity=video.broadcasting_entity or "",
        date=video.schedule_time or "", duration=video.duration or "", status="new"
    )


def _build_create_response(video_id: int, video: VideoCreate) -> VideoResponse:
    """Сборка ответа после создания."""
    return VideoResponse(
        id=video_id, title=video.title, url=video.url,
        date=video.schedule_time or "", description=video.description or "",
        category=video.category or "", thumbnail=video.thumbnail or "",
        tags=video.tags or "", duration=video.duration or "",
        status="new", source_date=video.source_date or ""
    )
