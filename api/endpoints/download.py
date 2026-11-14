# download.py — Эндпоинты загрузки и управления
import io
import sys
import threading
from fastapi import APIRouter, HTTPException
from database import Database
from downloader import VideoDownloader

router = APIRouter()

# Импортируем глобальное состояние из main
from ..state import download_state


@router.post("/{video_id}/download")
async def download_video(video_id: int):
    """Запустить загрузку видео."""
    db = Database()
    video = db.get_video(video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Видео не найдено")
    
    stop_event = threading.Event()
    download_state[video_id] = {"stop_event": stop_event, "running": True}
    db.append_download_log(video_id, "download", "Начало загрузки видео...", "running")
    
    thread = threading.Thread(target=_run_download, args=(video_id, video, stop_event))
    thread.start()
    return {"message": "Загрузка видео начата", "video_id": video_id}


def _run_download(video_id: int, video, stop_event: threading.Event):
    """Фоновая задача загрузки."""
    db = Database()
    old_stdout = sys.stdout
    sys.stdout = captured = io.StringIO()
    
    try:
        with VideoDownloader(headless=True) as downloader:
            success, output = downloader.download_full(
                video.un_video_url,
                progress_callback=lambda s, m: _on_progress(db, video_id, s, m),
                stop_event=stop_event
            )
            _handle_download_result(db, video_id, video, success, output, stop_event)
    except Exception as e:
        db.append_download_log(video_id, "download", f"Ошибка: {str(e)}", "failed")
    finally:
        sys.stdout = old_stdout
        if video_id in download_state:
            download_state[video_id]["running"] = False


def _on_progress(db, video_id: int, status: str, message: str):
    """Колбэк прогресса загрузки."""
    db.append_download_log(video_id, "download", message, status)


def _handle_download_result(db, video_id: int, video, success: bool, output: str, stop_event: threading.Event):
    """Обработка результата загрузки."""
    if stop_event.is_set():
        db.update_video(video_id, status="partial")
        db.append_download_log(video_id, "download", "Загрузка остановлена пользователем. Видео частично скачано.", "failed")
        return
    
    if success and output:
        update_data = {"local_video_path": output, "status": "downloaded"}
        if not video.date and video.source_date:
            update_data["date"] = video.source_date
        db.update_video(video_id, **update_data)
        date_info = f", дата: {update_data.get('date', 'не указана')}"
        db.append_download_log(video_id, "download", f"Видео успешно загружено: {output}{date_info}", "completed")
    else:
        db.append_download_log(video_id, "download", f"Ошибка загрузки: {output}", "failed")


@router.post("/{video_id}/download/stop")
async def stop_download(video_id: int):
    """Остановить загрузку видео."""
    if video_id in download_state:
        download_state[video_id]["stop_event"].set()
        return {"message": "Загрузка остановлена", "video_id": video_id}
    return {"message": "Загрузка не найдена", "video_id": video_id}, 404


@router.post("/{video_id}/concat")
async def concat_video(video_id: int):
    """Склеить сегменты видео."""
    db = Database()
    video = db.get_video(video_id)
    if not video:
        raise HTTPException(status_code=404, detail="Видео не найдено")
    
    db.append_download_log(video_id, "download", "Начало склейки сегментов...", "running")
    thread = threading.Thread(target=_run_concat, args=(video_id, video))
    thread.start()
    return {"message": "Склейка видео начата", "video_id": video_id}


def _run_concat(video_id: int, video):
    """Фоновая задача склейки."""
    db = Database()
    try:
        with VideoDownloader(headless=True) as downloader:
            output = downloader.concat_segments(video.un_video_url)
            if output:
                db.update_video(video_id, local_video_path=output, status="downloaded")
                db.append_download_log(video_id, "download", f"Видео склеено: {output}", "completed")
            else:
                db.append_download_log(video_id, "download", "Не удалось склеить видео", "failed")
    except Exception as e:
        db.append_download_log(video_id, "download", f"Ошибка при склейке: {str(e)}", "failed")
