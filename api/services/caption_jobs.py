"""Очередь фоновой подготовки таймкодированных субтитров."""

import uuid
from concurrent.futures import ThreadPoolExecutor

from api.services.caption_job_callbacks import partial_callback, progress_callback
from api.services.caption_job_state import (
    create_job,
    drop_job,
    get_job,
    release_job,
    update_job,
)
from api.services.caption_pipeline import prepare_captions
from api.services.caption_repository import CaptionRepository

_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="caption-job")


def start_job(video_url: str, mode: str, identity: dict[str, str]) -> dict:
    """Создаёт задачу для cache key или возвращает уже выполняющуюся задачу."""
    cache_key = identity["cache_key"]
    job = create_job(
        uuid.uuid4().hex,
        cache_key,
        {
            "status": "queued",
            "progress": 0,
            "message": "Задача ожидает обработки",
            "cues": [],
            "asset_key": identity["asset_key"],
            "cache_key": cache_key,
            "mode": mode,
            "model": identity["model"],
            "language": identity["language"],
            "translate_to": identity.get("translate_to", ""),
            "translation_engine": identity.get("translation_engine", ""),
            "blocks_done": 0,
        },
    )
    if job["status"] != "queued" or job.get("started"):
        return job
    try:
        CaptionRepository().save_cues(
            cache_key,
            identity["asset_key"],
            mode,
            identity["model"],
            identity["language"],
            [],
            is_complete=False,
        )
        update_job(job["job_id"], started=True)
    except Exception:
        drop_job(job["job_id"], cache_key)
        raise
    _executor.submit(_run_job, job["job_id"], video_url)
    return get_job(job["job_id"])


def _run_job(job_id: str, video_url: str) -> None:
    """Скачивает запись, распознаёт фразы, переводит и сохраняет результат."""
    job = get_job(job_id)
    if not job:
        return
    update_job(job_id, status="downloading", message="Подключаюсь к видеопотоку", progress=5)
    try:
        cues = prepare_captions(
            video_url,
            job["mode"],
            job["asset_key"],
            progress_callback(job_id),
            partial_callback(job_id),
            job["translate_to"],
            job["translation_engine"],
        )
        CaptionRepository().save_cues(
            job["cache_key"],
            job["asset_key"],
            job["mode"],
            job["model"],
            job["language"],
            cues,
            is_complete=True,
        )
        update_job(job_id, status="complete", message="Субтитры готовы", progress=100, cues=[])
    except Exception as error:
        update_job(job_id, status="failed", message=str(error), progress=0)
    finally:
        release_job(job["cache_key"], job_id)


__all__ = ["start_job", "get_job"]
