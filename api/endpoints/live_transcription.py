"""Потоковая транскрибация коротких аудиофрагментов."""

import asyncio
import importlib.util
import logging
import os
import tempfile
import threading
from pathlib import Path

import requests
from fastapi import APIRouter, HTTPException, Request

router = APIRouter(prefix="/live-transcription", tags=["live-transcription"])
logger = logging.getLogger(__name__)
MAX_CHUNK_BYTES = 2_000_000
_model = None
_model_lock = threading.Lock()


@router.get("/health")
def health(mode: str = "local") -> dict:
    """Возвращает доступность выбранного режима распознавания."""
    if mode not in {"local", "cloud"}:
        raise HTTPException(status_code=400, detail="mode должен быть local или cloud")
    if mode == "cloud" and not os.getenv("OPENAI_API_KEY"):
        return {"ready": False, "mode": mode, "detail": "OPENAI_API_KEY не задан"}
    if mode == "local" and importlib.util.find_spec("whisperx") is None:
        return {"ready": False, "mode": mode, "detail": "Установите WhisperX для локального режима"}
    return {"ready": True, "mode": mode}


@router.post("/chunk")
async def transcribe_chunk(request: Request, mode: str = "local") -> dict:
    """Распознаёт WAV-фрагмент локально или через OpenAI-совместимый API."""
    content_length = request.headers.get("content-length")
    if content_length and content_length.isdigit() and int(content_length) > MAX_CHUNK_BYTES:
        raise HTTPException(status_code=413, detail="Размер WAV-фрагмента должен быть до 2 МБ")
    audio = await request.body()
    if not audio or len(audio) > MAX_CHUNK_BYTES:
        raise HTTPException(status_code=413, detail="Размер WAV-фрагмента должен быть до 2 МБ")
    if not audio.startswith(b"RIFF") or b"WAVE" not in audio[:16]:
        raise HTTPException(status_code=415, detail="Ожидается WAV-фрагмент")
    if mode not in {"local", "cloud"}:
        raise HTTPException(status_code=400, detail="mode должен быть local или cloud")

    try:
        text = await asyncio.to_thread(_transcribe, audio, mode)
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    except requests.RequestException as error:
        logger.warning("Ошибка облачной транскрибации: %s", error)
        raise HTTPException(status_code=502, detail="Облачный сервис распознавания недоступен") from error
    return {"text": text, "mode": mode}


def _transcribe(audio: bytes, mode: str) -> str:
    """Передаёт временный WAV-файл выбранному движку и возвращает распознанный текст."""
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as audio_file:
        audio_file.write(audio)
        audio_path = Path(audio_file.name)
    try:
        if mode == "cloud":
            return _transcribe_cloud(audio_path)
        return _transcribe_local(audio_path)
    finally:
        audio_path.unlink(missing_ok=True)


def _transcribe_cloud(audio_path: Path) -> str:
    """Отправляет WAV в OpenAI-совместимый endpoint транскрибации."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("Для облачного режима задайте OPENAI_API_KEY")
    base_url = os.getenv("OPENAI_URL", "https://api.openai.com/v1").rstrip("/")
    model_name = os.getenv("LIVE_ASR_MODEL", "whisper-1")
    with audio_path.open("rb") as audio_file:
        response = requests.post(
            f"{base_url}/audio/transcriptions",
            headers={"Authorization": f"Bearer {api_key}"},
            data={"model": model_name, "language": "en", "response_format": "json"},
            files={"file": (audio_path.name, audio_file, "audio/wav")},
            timeout=90,
        )
    response.raise_for_status()
    return str(response.json().get("text", "")).strip()


def _transcribe_local(audio_path: Path) -> str:
    """Распознаёт WAV через один переиспользуемый экземпляр WhisperX."""
    global _model
    try:
        import whisperx
    except ImportError as error:
        raise RuntimeError("Установите WhisperX для локального режима") from error
    with _model_lock:
        if _model is None:
            model_name = os.getenv("LIVE_WHISPER_MODEL", "small")
            _model = whisperx.load_model(model_name, device="cpu", compute_type="int8")
        result = _model.transcribe(str(audio_path), language="en", batch_size=4)
    return " ".join(
        segment.get("text", "").strip()
        for segment in result.get("segments", [])
        if segment.get("text")
    ).strip()
