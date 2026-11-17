"""Стабильные идентификаторы аудиоархивов и результатов распознавания."""

import hashlib
import json
import os
from urllib.parse import urlsplit, urlunsplit

PIPELINE_VERSION = "2"


def cache_identity(
    video_url: str,
    mode: str,
    translate_to: str = "",
    translation_engine: str = "",
    live_stream: bool = False,
) -> dict[str, str]:
    """Формирует ключи архива и транскрипции с учётом распознавания и перевода."""
    canonical_url = _canonical_url(video_url)
    asset_key = _digest(canonical_url)
    if mode == "local":
        model = os.getenv("LIVE_WHISPER_MODEL", "small")
    else:
        endpoint = _safe_endpoint(os.getenv("OPENAI_URL", "https://api.openai.com/v1"))
        model = f"{endpoint}:{os.getenv('LIVE_ASR_MODEL', 'whisper-1')}"
    cache_payload = {
        "asset_key": asset_key,
        "mode": mode,
        "model": model,
        "language": "en",
        "translate_to": translate_to,
        "translation_engine": translation_engine if translate_to else "",
        "pipeline_version": PIPELINE_VERSION,
    }
    if live_stream:
        cache_payload["source_mode"] = "live"
    cache_key = _digest(json.dumps(cache_payload, sort_keys=True))
    return {
        "canonical_url": canonical_url,
        "asset_key": asset_key,
        "cache_key": cache_key,
        "model": model,
        "language": "en",
        "translate_to": translate_to,
        "translation_engine": translation_engine if translate_to else "",
    }


def _canonical_url(video_url: str) -> str:
    """Убирает query, fragment и завершающий slash из адреса video asset."""
    parts = urlsplit(video_url)
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/"), "", ""))


def _digest(value: str) -> str:
    """Возвращает SHA-256 hex-идентификатор строки."""
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _safe_endpoint(value: str) -> str:
    """Оставляет в идентификаторе облачного ASR адрес без credentials и query."""
    parts = urlsplit(value)
    hostname = parts.hostname or ""
    if parts.port:
        hostname = f"{hostname}:{parts.port}"
    return urlunsplit((parts.scheme.lower(), hostname.lower(), parts.path.rstrip("/"), "", ""))
