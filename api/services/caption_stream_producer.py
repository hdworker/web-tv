"""HLS producer с ограниченной очередью ASR-блоков."""

import queue
import threading
from pathlib import Path
from typing import Iterator

from api.services.caption_asr import Progress
from api.services.caption_media import archive_segments
from api.services.caption_segmenter import SEGMENT_WINDOW, AudioSegment, download_segments

FIRST_BATCH_SECONDS = 30
ASR_BATCH_SECONDS = 120
QUEUE_WINDOWS = 2


def produce_batches(
    video_url: str,
    asset_key: str,
    workdir: Path,
    batches: queue.Queue,
    cancelled: threading.Event,
    progress: Progress,
) -> None:
    """Скачивает окна HLS, публикует ASR-блоки и сохраняет полный FLAC."""
    all_segments: list[AudioSegment] = []
    try:
        for batch in _iter_batches(video_url, workdir, all_segments, progress, cancelled):
            if cancelled.is_set():
                return
            if not _put_batch(batches, batch, cancelled):
                return
        if not all_segments:
            raise RuntimeError("В аудиопотоке не найдено сегментов")
        archive_segments(
            video_url,
            asset_key,
            [segment.path for segment in all_segments],
            workdir,
            progress,
        )
        _put_batch(batches, ("done",), cancelled)
    except Exception as error:
        _put_batch(batches, ("error", str(error)), cancelled)


def _iter_batches(
    video_url: str,
    workdir: Path,
    all_segments: list[AudioSegment],
    progress: Progress,
    cancelled: threading.Event,
) -> Iterator[tuple]:
    """Отдаёт первый короткий блок, затем блоки по две минуты."""
    pending: list[AudioSegment] = []
    pending_duration = 0.0
    target = FIRST_BATCH_SECONDS
    batch_start = 0.0
    for segment in download_segments(video_url, workdir / "segments"):
        if cancelled.is_set():
            return
        all_segments.append(segment)
        if not pending:
            batch_start = segment.start
        pending.append(segment)
        pending_duration += segment.duration
        _report_window_progress(len(all_segments), progress)
        if pending_duration >= target:
            yield ("audio", pending, batch_start)
            pending = []
            pending_duration = 0.0
            target = ASR_BATCH_SECONDS
    if pending:
        yield ("audio", pending, batch_start)


def _report_window_progress(count: int, progress: Progress) -> None:
    """Публикует накопительный счётчик после каждого окна из девяти."""
    if count % SEGMENT_WINDOW == 0:
        progress(f"Скачано аудиосегментов: {count}", None)


def _put_batch(
    batches: queue.Queue,
    item: tuple,
    cancelled: threading.Event,
) -> bool:
    """Помещает блок в ограниченную очередь с поддержкой отмены."""
    while not cancelled.is_set():
        try:
            batches.put(item, timeout=0.5)
            return True
        except queue.Full:
            continue
    return False
