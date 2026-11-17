"""Распознавание, перевод и остановка сегментов live-аудио."""

import subprocess
import threading
from pathlib import Path
from typing import Any, Callable

from api.services.caption_asr import transcribe_cloud, transcribe_local
from api.services.caption_ffmpeg import probe_duration
from api.services.translation_engines import attach_translations

Progress = Callable[[str, int | None], None]
OnBatch = Callable[[int, list[dict]], None]
MAX_PENDING_SEGMENTS = 10


def consume_segments(
    process: subprocess.Popen,
    workdir: Path,
    mode: str,
    model: Any,
    stop_event: threading.Event,
    progress: Progress,
    on_batch: OnBatch,
    translate_to: str,
    translation_engine: str,
) -> list[dict]:
    """Обрабатывает WAV-блоки до остановки FFmpeg или пользователя."""
    cues = []
    processed: set[Path] = set()
    offset = 0.0
    number = 0
    while process.poll() is None or has_pending_chunks(workdir, processed):
        if stop_event.is_set() and process.poll() is None:
            stop_process(process)
        ready = _ready_segments(workdir, processed, process.poll() is not None)
        if len(ready) > MAX_PENDING_SEGMENTS:
            raise RuntimeError("Распознавание отстаёт от эфира; задача остановлена")
        if ready:
            batch_cues, offset, number = _process_segments(
                ready, mode, model, offset, number, progress, on_batch,
                translate_to, translation_engine,
            )
            processed.update(ready)
            cues.extend(batch_cues)
        elif process.poll() is None:
            stop_event.wait(0.5)
        else:
            break
    if process.returncode not in (0, None) and not stop_event.is_set():
        raise RuntimeError("FFmpeg потерял live HLS-поток")
    return cues


def _ready_segments(workdir: Path, processed: set[Path], finished: bool) -> list[Path]:
    """Возвращает завершённые WAV-блоки, не читая текущий открытый файл."""
    pending = [path for path in sorted(workdir.glob("live-*.wav")) if path not in processed]
    return pending if finished else pending[:-1]


def _process_segments(
    paths: list[Path],
    mode: str,
    model: Any,
    offset: float,
    number: int,
    progress: Progress,
    on_batch: OnBatch,
    translate_to: str,
    translation_engine: str,
) -> tuple[list[dict], float, int]:
    """Распознаёт, переводит и публикует готовые WAV-блоки."""
    cues = []
    for path in paths:
        batch, duration = _transcribe_segment(path, mode, model, offset, progress)
        path.unlink(missing_ok=True)
        offset += duration
        number += 1
        batch = attach_translations(batch, translate_to, translation_engine, progress)
        cues.extend(batch)
        on_batch(number, batch)
    return cues, offset, number


def _transcribe_segment(
    path: Path,
    mode: str,
    model: Any,
    offset: float,
    progress: Progress,
) -> tuple[list[dict], float]:
    """Распознаёт один WAV-блок и возвращает его длительность."""
    duration = probe_duration(path)
    progress(f"Распознаю live-блок с позиции {offset:.1f} с", None)
    if mode == "local":
        return transcribe_local(path, model, offset), duration
    return transcribe_cloud(path, progress, offset), duration


def has_pending_chunks(workdir: Path, processed: set[Path]) -> bool:
    """Проверяет, остались ли WAV-блоки после завершения FFmpeg."""
    return any(path not in processed for path in workdir.glob("live-*.wav"))


def stop_process(process: subprocess.Popen) -> None:
    """Останавливает FFmpeg и не оставляет дочерний процесс после ошибки."""
    if process.poll() is not None:
        return
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)
