"""Ограниченный producer-consumer конвейер загрузки сегментов и ASR."""

import queue
import tempfile
import threading
from pathlib import Path
from typing import Any, Callable

from api.services.caption_asr import (
    Progress,
    load_local_model,
    transcribe_cloud,
    transcribe_local,
)
from api.services.caption_media import concatenate_segments
from api.services.caption_stream_producer import QUEUE_WINDOWS, produce_batches
from transcriber import VideoTranscriber

OnBatch = Callable[[int, list[dict]], None]


def download_and_transcribe(
    video_url: str,
    mode: str,
    asset_key: str,
    progress: Progress,
    on_batch: OnBatch,
) -> list[dict]:
    """Перекрывает скачивание HLS-окон из девяти сегментов с ASR."""
    with tempfile.TemporaryDirectory(prefix="webtv-stream-") as folder:
        workdir = Path(folder)
        batches: queue.Queue = queue.Queue(maxsize=QUEUE_WINDOWS)
        cancelled = threading.Event()
        producer = threading.Thread(
            target=produce_batches,
            args=(video_url, asset_key, workdir, batches, cancelled, progress),
            daemon=True,
        )
        producer.start()
        try:
            return _consume_batches(mode, workdir, batches, cancelled, progress, on_batch)
        finally:
            cancelled.set()
            producer.join()


def _consume_batches(
    mode: str,
    workdir: Path,
    batches: queue.Queue,
    cancelled: threading.Event,
    progress: Progress,
    on_batch: OnBatch,
) -> list[dict]:
    """Распознаёт ASR-блоки одной моделью, пока producer качает следующие."""
    model: Any = load_local_model(progress) if mode == "local" else None
    cues = []
    batch_number = 0
    while True:
        item = batches.get()
        if item[0] == "error":
            raise RuntimeError(item[1])
        if item[0] == "done":
            break
        _, segments, offset = item
        batch_number += 1
        ts_path = concatenate_segments(
            [segment.path for segment in segments],
            workdir,
            f"asr-{batch_number}.ts",
        )
        wav_path = _extract_wav(ts_path, workdir, f"asr-{batch_number}.wav")
        progress(f"Распознаю аудиоблок {batch_number} с позиции {offset:.1f} с", None)
        if mode == "local":
            batch_cues = transcribe_local(wav_path, model, offset)
        else:
            batch_cues = transcribe_cloud(wav_path, progress, offset)
        cues.extend(batch_cues)
        on_batch(batch_number, batch_cues)
    return sorted(cues, key=lambda cue: (cue["start"], cue["end"]))


def _extract_wav(media_path: Path, workdir: Path, name: str) -> Path:
    """Извлекает временный WAV из TS-блока."""
    wav_path = workdir / name
    if not VideoTranscriber().extract_audio(str(media_path), str(wav_path)):
        raise RuntimeError("Не удалось подготовить аудио для распознавания")
    return wav_path
