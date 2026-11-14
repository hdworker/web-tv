# main.py — Точка входа для роутера видео
import logging
from fastapi import APIRouter

from .endpoints import (
    caption_preparation,
    caption_tts,
    create,
    download,
    live_transcription,
    read,
    transcribe,
    utils,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/videos", tags=["videos"])

# Подключаем все эндпоинты
router.include_router(read.router)
router.include_router(create.router)
router.include_router(download.router)
router.include_router(transcribe.router)
router.include_router(utils.router)
router.include_router(live_transcription.router)
router.include_router(caption_preparation.router)
router.include_router(caption_tts.router)

__all__ = ["router"]
# download_state больше НЕ здесь — импортируйте из .state при необходимости
