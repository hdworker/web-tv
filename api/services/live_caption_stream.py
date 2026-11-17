"""Получение аудио прямого HLS-эфира и потоковая подготовка фраз."""

import subprocess
import tempfile
import threading
from pathlib import Path
from typing import Callable

from api.services.caption_asr import load_local_model
from api.services.live_hls import resolve_live_audio_playlist
from api.services.live_caption_segments import (
    consume_segments,
    stop_process,
)

Progress = Callable[[str, int | None], None]
OnBatch = Callable[[int, list[dict]], None]
SEGMENT_SECONDS = 12


def prepare_live_captions(
    video_url: str,
    mode: str,
    stop_event: threading.Event | None,
    progress: Progress,
    on_batch: OnBatch,
    translate_to: str = "",
    translation_engine: str = "opus",
) -> list[dict]:
    """Читает HLS-эфир до остановки или завершения, возвращая таймкодированные фразы."""
    stop_event = stop_event or threading.Event()
    if stop_event.is_set():
        raise RuntimeError("Захват прямого эфира остановлен пользователем")
    source = resolve_live_audio_playlist(video_url)
    progress(f"Подключена аудиодорожка: {source['name']}", None)
    if stop_event.is_set():
        raise RuntimeError("Захват прямого эфира остановлен пользователем")
    cues = _capture_audio(
        source["url"],
        video_url,
        mode,
        stop_event,
        progress,
        on_batch,
        translate_to,
        translation_engine,
    )
    if not cues:
        raise RuntimeError("Эфир остановлен до получения первого распознанного блока")
    return cues


def _capture_audio(
    audio_url: str,
    referer: str,
    mode: str,
    stop_event: threading.Event,
    progress: Progress,
    on_batch: OnBatch,
    translate_to: str,
    translation_engine: str,
) -> list[dict]:
    """Запускает FFmpeg и передаёт готовые блоки на распознавание."""
    with tempfile.TemporaryDirectory(prefix="webtv-live-") as folder:
        workdir = Path(folder)
        process = _start_ffmpeg(audio_url, referer, workdir)
        try:
            model = load_local_model(progress) if mode == "local" else None
            cues = consume_segments(
                process,
                workdir,
                mode,
                model,
                stop_event,
                progress,
                on_batch,
                translate_to,
                translation_engine,
            )
        finally:
            stop_process(process)
    return cues


def _start_ffmpeg(audio_url: str, referer: str, workdir: Path) -> subprocess.Popen:
    """Запускает HLS-демультиплексор с ограниченными WAV-блоками в каталоге задачи."""
    pattern = workdir / "live-%06d.wav"
    command = [
        "ffmpeg", "-hide_banner", "-loglevel", "error",
        "-user_agent", "Mozilla/5.0",
        "-headers", f"Referer: {referer}\r\n",
        "-rw_timeout", "30000000",
        "-live_start_index", "-1",
        "-i", audio_url,
        "-map", "0:a:0", "-vn", "-acodec", "pcm_s16le",
        "-ar", "16000", "-ac", "1",
        "-f", "segment", "-segment_time", str(SEGMENT_SECONDS),
        "-reset_timestamps", "1", "-segment_format", "wav",
        str(pattern),
    ]
    try:
        return subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except OSError as error:
        raise RuntimeError("Не удалось запустить FFmpeg для live HLS") from error
