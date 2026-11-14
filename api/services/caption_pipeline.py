"""Подготовка архивированного FLAC к транскрибации и переводу."""

import tempfile
from pathlib import Path
from typing import Callable

from api.services.caption_asr import Progress, load_local_model, transcribe_cloud, transcribe_local
from api.services.caption_ffmpeg import probe_duration, split_wav_chunks
from api.services.caption_media import get_saved_audio
from api.services.caption_stream import download_and_transcribe
from api.services.translation_engines import attach_translations

OnBatch = Callable[[int, list[dict]], None]


def prepare_captions(
    video_url: str,
    mode: str,
    asset_key: str,
    progress: Progress,
    on_batch: OnBatch,
    translate_to: str = "",
    translation_engine: str = "opus",
) -> list[dict]:
    """Готовит фразы из архива или из HLS-потока, добавляя перевод."""
    def publish(number: int, batch: list[dict]) -> None:
        """Переводит готовый блок и передаёт его дальше."""
        translated = attach_translations(batch, translate_to, translation_engine, progress)
        on_batch(number, translated)

    audio_path = get_saved_audio(asset_key)
    if audio_path:
        cues = _transcribe_saved_audio(audio_path, mode, progress, publish)
    else:
        cues = download_and_transcribe(video_url, mode, asset_key, progress, publish)
    if translate_to:
        cues = attach_translations(cues, translate_to, translation_engine, progress)
    if not cues:
        raise RuntimeError("Распознаватель не вернул фразы")
    return cues


def _transcribe_saved_audio(
    audio_path: Path,
    mode: str,
    progress: Progress,
    on_batch: OnBatch,
) -> list[dict]:
    """Повторно распознаёт сохранённый FLAC без загрузки HLS-сегментов."""
    with tempfile.TemporaryDirectory(prefix="webtv-asr-") as folder:
        workdir = Path(folder)
        chunks = split_wav_chunks(audio_path, workdir)
        model = load_local_model(progress) if mode == "local" else None
        cues = []
        offset = 0.0
        for number, chunk in enumerate(chunks, start=1):
            progress(f"Распознаю аудиоблок {number} с позиции {offset:.1f} с", None)
            batch = (
                transcribe_local(chunk, model, offset)
                if mode == "local"
                else transcribe_cloud(chunk, progress, offset)
            )
            cues.extend(batch)
            on_batch(number, batch)
            offset += probe_duration(chunk)
        return cues
