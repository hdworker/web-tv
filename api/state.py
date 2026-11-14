# state.py — Глобальное состояние (без зависимостей)
import threading
from typing import Dict, Any

# video_id -> {"stop_event": threading.Event, "running": bool}
download_state: Dict[int, Dict[str, Any]] = {}

def create_stop_event(video_id: int) -> threading.Event:
    """Создаёт и регистрирует событие остановки."""
    event = threading.Event()
    download_state[video_id] = {"stop_event": event, "running": True}
    return event

def is_running(video_id: int) -> bool:
    """Проверяет, запущена ли загрузка."""
    return download_state.get(video_id, {}).get("running", False)

def stop_download(video_id: int) -> bool:
    """Останавливает загрузку по video_id."""
    if video_id not in download_state:
        return False
    download_state[video_id]["stop_event"].set()
    download_state[video_id]["running"] = False
    return True

def mark_completed(video_id: int):
    """Помечает загрузку как завершённую."""
    if video_id in download_state:
        download_state[video_id]["running"] = False

__all__ = ["download_state", "create_stop_event", "is_running", "stop_download", "mark_completed"]