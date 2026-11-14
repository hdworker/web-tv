# models.py — Pydantic-модели для видео
from typing import Optional, List
from pydantic import BaseModel


class VideoCreate(BaseModel):
    """Модель создания видео."""
    url: str
    title: str
    source_date: Optional[str] = ""
    description: Optional[str] = ""
    category: Optional[str] = ""
    thumbnail: Optional[str] = ""
    tags: Optional[str] = ""
    broadcasting_entity: Optional[str] = ""
    duration: Optional[str] = ""
    schedule_time: Optional[str] = ""


class VideoResponse(BaseModel):
    """Модель ответа с данными видео."""
    id: int
    title: str
    url: str
    date: str
    description: str
    category: str
    thumbnail: str
    tags: str
    duration: str
    status: str
    source_date: str
    local_video_path: Optional[str] = None


class DownloadLogResponse(BaseModel):
    """Модель ответа с логами загрузки."""
    id: int
    video_id: int
    action: str
    log_text: str
    status: str
    created_at: str


__all__ = ["VideoCreate", "VideoResponse", "DownloadLogResponse"]
