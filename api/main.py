# main.py — Точка входа для роутера видео
import logging
from fastapi import APIRouter

from .endpoints import read, create, download, transcribe, utils

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/videos", tags=["videos"])

# Подключаем все эндпоинты
router.include_router(read.router)
router.include_router(create.router)
router.include_router(download.router)
router.include_router(transcribe.router)
router.include_router(utils.router)

__all__ = ["router"]
# download_state больше НЕ здесь — импортируйте из .state при необходимости