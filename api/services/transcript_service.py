# transcript_service.py — Сервис работы с транскриптами
import logging
from database import Database, Transcription
from transcript_extractor import extract_transcript_from_url

logger = logging.getLogger(__name__)


async def get_transcript(video_id: int) -> dict:
    """Получить транскрипт: из БД или со страницы."""
    db = Database()
    video = db.get_video(video_id)
    if not video:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Видео не найдено")
    
    logger.info(f"Запрос транскрипта для видео {video_id}")
    db.append_download_log(video_id, "transcript", "Начало получения транскрипта...", "running")
    
    existing = db.get_transcriptions(video_id)
    if existing and existing[0].transcript_text:
        return _return_from_db(existing[0])
    
    return await _fetch_and_save_transcript(db, video_id, video.un_video_url)


def _return_from_db(transcription) -> dict:
    """Возврат транскрипта из БД."""
    return {"transcript": transcription.transcript_text, "source": "database"}


async def _fetch_and_save_transcript(db, video_id: int, url: str) -> dict:
    """Получение и сохранение транскрипта со страницы."""
    db.append_download_log(video_id, "transcript", "Транскрипт не найден в БД, загрузка со страницы UN...", "running")
    transcript = extract_transcript_from_url(url, use_selenium=True)
    
    if transcript:
        return _save_transcript(db, video_id, transcript)
    else:
        db.append_download_log(video_id, "transcript", "Транскрипт не найден на странице видео", "failed")
        return {"transcript": "", "source": "not_found"}


def _save_transcript(db, video_id: int, transcript: str) -> dict:
    """Сохранение транскрипта в БД."""
    transcription = Transcription(video_id=video_id, transcript_text=transcript, language="en")
    db.add_transcription(transcription)
    db.append_download_log(video_id, "transcript", "Транскрипт сохранён в БД", "completed")
    return {"transcript": transcript, "source": "page"}
