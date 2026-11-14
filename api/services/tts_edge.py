"""Синтез речи Edge TTS с кешем готовых mp3."""

import asyncio
import hashlib
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

CACHE_DIR = Path("video") / "tts"
_voices: list[dict] | None = None


def synthesize(text: str, voice: str) -> Path:
    """Возвращает путь к mp3, синтезируя его при первом обращении."""
    text = text.strip()
    if not text:
        raise ValueError("Пустой текст для озвучки")
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha1(f"{voice}|{text}".encode("utf-8")).hexdigest()
    target = CACHE_DIR / f"{digest}.mp3"
    if target.is_file() and target.stat().st_size > 512:
        return target
    audio = _synthesize_with_fallback(text, voice)
    target.write_bytes(audio)
    return target


def _synthesize_with_fallback(text: str, voice: str) -> bytes:
    """Перебирает голоса той же локали: отдельные голоса иногда отдают пустой поток."""
    errors = []
    for candidate in _candidates(voice):
        try:
            audio = asyncio.run(_stream_audio(text, candidate))
        except Exception as error:
            errors.append(f"{candidate}: {error}")
            continue
        if len(audio) >= 512:
            return audio
        errors.append(f"{candidate}: пустой поток")
    raise RuntimeError("Edge TTS не озвучил фразу (" + "; ".join(errors) + ")")


def _candidates(voice: str) -> list[str]:
    """Возвращает запрошенный голос и запасные голоса его локали."""
    locale = voice.split("-")[0] if "-" not in voice else "-".join(voice.split("-")[:2])
    try:
        fallbacks = [item["name"] for item in list_voices(locale) if item["name"] != voice]
    except Exception:
        fallbacks = []
    return [voice, *fallbacks]


def list_voices(locale_prefix: str) -> list[dict]:
    """Возвращает доступные голоса Edge для нужной локали."""
    global _voices
    if _voices is None:
        _voices = asyncio.run(_fetch_voices())
    lower = locale_prefix.lower()
    return [
        {
            "name": item["ShortName"],
            "locale": item["Locale"],
            "gender": item.get("Gender", ""),
        }
        for item in _voices
        if item["Locale"].lower().startswith(lower)
    ]


async def _fetch_voices() -> list[dict]:
    """Загружает каталог голосов Microsoft Edge у сервиса Edge TTS."""
    import edge_tts

    return await edge_tts.list_voices()


async def _stream_audio(text: str, voice: str) -> bytes:
    """Собирает mp3-поток Edge TTS в один буфер."""
    import edge_tts

    communicate = edge_tts.Communicate(text, voice)
    buffer = bytearray()
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            buffer.extend(chunk["data"])
    logger.info("Edge TTS: %s символов, %s байт", len(text), len(buffer))
    return bytes(buffer)
