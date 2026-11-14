"""Адаптеры локального и облачного распознавания речи."""

import math
import os
import tempfile
import wave
from pathlib import Path
from typing import Any, Callable

import requests

Progress = Callable[[str, int | None], None]


def load_local_model(progress: Progress) -> Any:
    """Загружает одну копию локальной модели WhisperX для всей очереди блоков."""
    import whisperx

    model_name = os.getenv("LIVE_WHISPER_MODEL", "small")
    progress(f"Загружаю локальную модель WhisperX: {model_name}", None)
    return whisperx.load_model(model_name, device="cpu", compute_type="int8")


def transcribe_local(audio_path: Path, model: Any, offset: float = 0.0) -> list[dict]:
    """Распознаёт один WAV-блок и привязывает его фразы к общему таймлайну."""
    result = model.transcribe(str(audio_path), language="en", batch_size=4)
    return to_cues(result.get("segments", []), offset)


def transcribe_cloud(
    audio_path: Path,
    progress: Progress,
    offset: float = 0.0,
) -> list[dict]:
    """Распознаёт WAV через OpenAI-совместимый API с временными метками."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("Для облачного режима задайте OPENAI_API_KEY")
    base_url = os.getenv("OPENAI_URL", "https://api.openai.com/v1").rstrip("/")
    model_name = os.getenv("LIVE_ASR_MODEL", "whisper-1")
    return _transcribe_wav_chunks(audio_path, base_url, api_key, model_name, progress, offset)


def _transcribe_wav_chunks(
    audio_path: Path,
    base_url: str,
    api_key: str,
    model_name: str,
    progress: Progress,
    offset: float,
) -> list[dict]:
    """Распознаёт части WAV и смещает таймкоды к началу полной записи."""
    cues = []
    with wave.open(str(audio_path), "rb") as source:
        params = source.getparams()
        frames_per_chunk = params.framerate * 120
        total_chunks = math.ceil(params.nframes / frames_per_chunk)
        chunk_offset = offset
        chunk_number = 0
        while frames := source.readframes(frames_per_chunk):
            chunk_number += 1
            payload = _request_wav_chunk(frames, params, base_url, api_key, model_name)
            if not payload.get("segments"):
                raise RuntimeError("Облачный ASR не вернул временные метки фраз")
            cues.extend(to_cues(payload["segments"], chunk_offset))
            chunk_offset += len(frames) / (params.framerate * params.nchannels * params.sampwidth)
            progress(f"Облачный ASR: обработано {chunk_number}/{total_chunks} частей", None)
    return cues


def _request_wav_chunk(
    frames: bytes,
    params: Any,
    base_url: str,
    api_key: str,
    model_name: str,
) -> dict:
    """Сериализует WAV-часть, отправляет её ASR и возвращает JSON-ответ."""
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as chunk:
        chunk_path = Path(chunk.name)
    try:
        _write_wav_chunk(chunk_path, frames, params)
        return _send_wav_chunk(chunk_path, base_url, api_key, model_name)
    finally:
        chunk_path.unlink(missing_ok=True)


def _write_wav_chunk(path: Path, frames: bytes, params: Any) -> None:
    """Записывает PCM-кадры с исходными параметрами WAV."""
    with wave.open(str(path), "wb") as target:
        target.setnchannels(params.nchannels)
        target.setsampwidth(params.sampwidth)
        target.setframerate(params.framerate)
        target.writeframes(frames)


def _send_wav_chunk(path: Path, base_url: str, api_key: str, model_name: str) -> dict:
    """Отправляет временный WAV-фрагмент в облачный ASR."""
    with path.open("rb") as audio_file:
        response = requests.post(
            f"{base_url}/audio/transcriptions",
            headers={"Authorization": f"Bearer {api_key}"},
            data={"model": model_name, "language": "en", "response_format": "verbose_json"},
            files={"file": (path.name, audio_file, "audio/wav")},
            timeout=180,
        )
    response.raise_for_status()
    return response.json()


def to_cues(segments: list[dict], offset: float = 0.0) -> list[dict]:
    """Нормализует распознанные фразы к формату start/end/text."""
    return [
        {
            "start": round(float(segment.get("start", 0)) + offset, 3),
            "end": round(float(segment.get("end", 0)) + offset, 3),
            "text": segment.get("text", "").strip(),
        }
        for segment in segments
        if segment.get("text", "").strip()
        and float(segment.get("end", 0)) > float(segment.get("start", 0))
    ]
