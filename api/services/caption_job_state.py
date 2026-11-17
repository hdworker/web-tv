"""Разделяемое состояние задач подготовки субтитров."""

import threading
from typing import Any

JOBS: dict[str, dict] = {}
LOCK = threading.Lock()
ACTIVE: dict[str, str] = {}
STOP_EVENTS: dict[str, threading.Event] = {}


def create_job(job_id: str, cache_key: str, payload: dict[str, Any]) -> dict:
    """Регистрирует новую задачу и помечает её активной для ключа кеша."""
    with LOCK:
        current = ACTIVE.get(cache_key)
        if current and current in JOBS:
            return dict(JOBS[current])
        JOBS[job_id] = {"job_id": job_id, **payload, "version": 0}
        STOP_EVENTS[job_id] = threading.Event()
        ACTIVE[cache_key] = job_id
        return dict(JOBS[job_id])


def get_job(job_id: str) -> dict | None:
    """Возвращает копию состояния задачи или None."""
    with LOCK:
        job = JOBS.get(job_id)
        return dict(job) if job else None


def update_job(job_id: str, **values: Any) -> None:
    """Атомарно обновляет состояние задачи и увеличивает версию."""
    with LOCK:
        job = JOBS.get(job_id)
        if job:
            job.update(values)
            job["version"] += 1


def release_job(cache_key: str, job_id: str) -> None:
    """Снимает признак активной задачи, если он принадлежит этой задаче."""
    with LOCK:
        if ACTIVE.get(cache_key) == job_id:
            ACTIVE.pop(cache_key, None)


def drop_job(job_id: str, cache_key: str) -> None:
    """Удаляет неудачно созданную задачу из состояния."""
    with LOCK:
        JOBS.pop(job_id, None)
        STOP_EVENTS.pop(job_id, None)
        if ACTIVE.get(cache_key) == job_id:
            ACTIVE.pop(cache_key, None)


def request_stop(job_id: str) -> bool:
    """Запрашивает остановку активной задачи прямого эфира."""
    with LOCK:
        job = JOBS.get(job_id)
        stop_event = STOP_EVENTS.get(job_id)
        if not job or not job.get("live_stream") or not stop_event:
            return False
        if job.get("status") in {"complete", "failed"}:
            return False
        stop_event.set()
        return True


def get_stop_event(job_id: str) -> threading.Event | None:
    """Возвращает сигнал отмены активной задачи."""
    with LOCK:
        return STOP_EVENTS.get(job_id)


def clear_stop_event(job_id: str) -> None:
    """Удаляет сигнал остановки после завершения фоновой задачи."""
    with LOCK:
        STOP_EVENTS.pop(job_id, None)
