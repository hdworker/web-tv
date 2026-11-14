# transcribe.py — Эндпоинты транскрибации
import threading
from fastapi import APIRouter, HTTPException
from database import Database
from transcriber import VideoTranscriber

router = APIRouter()


@router.post("/{video_id}/transcribe")
async def transcribe_video(video_id: int):
    """Запустить транскрибацию видео."""
    db = Database()
    video = db.get_video(video_id)
    
    if not video:
        raise HTTPException(status_code=404, detail="Видео не найдено")
    if not video.local_video_path:
        raise HTTPException(status_code=400, detail="Видео не загружено")
    
    db.append_download_log(video_id, "transcribe", "Начало транскрибации...", "running")
    thread = threading.Thread(target=_run_transcribe, args=(video_id, video.local_video_path))
    thread.start()
    return {"message": "Транскрибация начата", "video_id": video_id}


def _run_transcribe(video_id: int, video_path: str):
    """Фоновая задача транскрибации."""
    db = Database()
    try:
        transcriber = VideoTranscriber()
        text = transcriber.transcribe(video_path)
        if text:
            db.update_video(video_id, status="transcribed")
            db.append_download_log(video_id, "transcribe", f"Транскрибация завершена ({len(text)} символов)", "completed")
        else:
            db.append_download_log(video_id, "transcribe", "Не удалось получить текст транскрипции", "failed")
    except Exception as e:
        db.append_download_log(video_id, "transcribe", f"Ошибка: {str(e)}", "failed")
