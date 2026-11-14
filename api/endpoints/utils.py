# utils.py — Вспомогательные эндпоинты (stream, open-folder)
import os
import re
import platform
import subprocess
import logging
from fastapi import APIRouter, HTTPException, Response, Request
from database import Database

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/{video_id}/open-folder")
async def open_video_folder(video_id: int):
    """Открыть папку с видео."""
    db = Database()
    video = db.get_video(video_id)
    
    if not video:
        raise HTTPException(status_code=404, detail="Видео не найдено")
    if not video.local_video_path:
        raise HTTPException(status_code=400, detail="Видео не загружено")
    
    folder_path = os.path.dirname(video.local_video_path)
    if not os.path.exists(folder_path):
        raise HTTPException(status_code=404, detail="Папка не найдена")
    
    return _open_folder(folder_path)


def _open_folder(folder_path: str) -> dict:
    """Открытие папки в зависимости от ОС."""
    try:
        if platform.system() == "Windows":
            subprocess.Popen(["explorer", folder_path])
        elif platform.system() == "Darwin":
            subprocess.Popen(["open", folder_path])
        else:
            subprocess.Popen(["xdg-open", folder_path])
        logger.info(f"Открыта папка: {folder_path}")
        return {"message": "Папка открыта", "folder": folder_path}
    except Exception as e:
        logger.error(f"Ошибка открытия папки: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{video_id}/stream")
async def stream_video(video_id: int, request: Request):
    """Потоковая передача видео."""
    db = Database()
    video = db.get_video(video_id)
    
    if not video:
        raise HTTPException(status_code=404, detail="Видео не найдено")
    if not video.local_video_path or not os.path.exists(video.local_video_path):
        raise HTTPException(status_code=404, detail="Видеофайл не найден")
    
    return _build_stream_response(video.local_video_path, request)


def _build_stream_response(file_path: str, request: Request) -> Response:
    """Построение ответа для стриминга."""
    file_size = os.path.getsize(file_path)
    range_header = request.headers.get("range")
    start, end, chunk_size = _parse_range(range_header, file_size)
    
    return Response(
        content=_iter_file(file_path, start, chunk_size),
        status_code=206 if range_header else 200,
        media_type="video/mp4",
        headers={
            "Accept-Ranges": "bytes",
            "Content-Range": f"bytes {start}-{end}/{file_size}",
            "Content-Length": str(chunk_size),
        }
    )


def _parse_range(range_header: str, file_size: int) -> tuple:
    """Парсинг заголовка Range."""
    if not range_header:
        return 0, file_size - 1, file_size
    match = re.match(r"bytes=(\d+)-(\d*)", range_header)
    if match:
        start = int(match.group(1))
        end = int(match.group(2)) if match.group(2) else file_size - 1
    else:
        start, end = 0, file_size - 1
    return start, end, end - start + 1


def _iter_file(file_path: str, start: int, total_bytes: int):
    """Генератор для чтения файла частями."""
    with open(file_path, "rb") as f:
        f.seek(start)
        remaining = total_bytes
        while remaining > 0:
            read_size = min(8192, remaining)
            chunk = f.read(read_size)
            if not chunk:
                break
            remaining -= len(chunk)
            yield chunk
