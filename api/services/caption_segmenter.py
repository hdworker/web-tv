"""Параллельная загрузка пронумерованных аудиосегментов Kaltura."""

import os
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator
from urllib.parse import urlsplit, urlunsplit

import requests

from api.services.caption_ffmpeg import probe_duration
from downloader import VideoDownloader

SEGMENT_WINDOW = 9


@dataclass(frozen=True)
class AudioSegment:
    number: int
    path: Path
    duration: float
    start: float


def download_segments(
    video_url: str,
    output_dir: Path,
) -> Iterator[AudioSegment]:
    """Находит audio-only HLS base и выдаёт сегменты с абсолютными смещениями."""
    output_dir.mkdir(parents=True, exist_ok=True)
    with VideoDownloader(headless=True) as downloader:
        base_url = downloader.get_video_url(video_url, audio_only=True)
    if not base_url:
        raise RuntimeError("Не удалось найти HLS-поток на странице UN Web TV")

    next_number = 1
    timeline_start = 0.0
    downloaded_count = 0
    with ThreadPoolExecutor(max_workers=SEGMENT_WINDOW) as pool:
        while True:
            window, reached_end = _download_window(
                pool,
                base_url,
                next_number,
                output_dir,
            )
            if not window and downloaded_count == 0:
                raise RuntimeError("Не удалось скачать аудиосегменты")
            for number, path, duration in window:
                yield AudioSegment(number, path, duration, timeline_start)
                timeline_start += duration
                downloaded_count += 1
            if reached_end:
                return
            next_number += SEGMENT_WINDOW


def _download_window(
    pool: ThreadPoolExecutor,
    base_url: str,
    first_number: int,
    output_dir: Path,
) -> tuple[list[tuple[int, Path, float]], bool]:
    """Загружает до девяти соседних сегментов параллельно и проверяет конец."""
    numbers = range(first_number, first_number + SEGMENT_WINDOW)
    results = list(
        pool.map(lambda number: _download_segment(base_url, number, output_dir), numbers)
    )
    available = [item for item in results if item is not None]
    missing = [first_number + index for index, item in enumerate(results) if item is None]
    if missing:
        first_missing = min(missing)
        if any(number > first_missing for number, _, _ in available):
            raise RuntimeError("В HLS-потоке обнаружен пропуск номера сегмента")
    return available, bool(missing)


def _download_segment(
    base_url: str,
    number: int,
    output_dir: Path,
) -> tuple[int, Path, float] | None:
    """Скачивает, проверяет и атомарно сохраняет один подписанный TS-сегмент."""
    target = output_dir / f"seg-{number}-a1.ts"
    temporary = output_dir / f".seg-{number}-a1.part.ts"
    url = _segment_url(base_url, number)
    for attempt in range(3):
        try:
            result = _fetch_segment(url, temporary)
            if result == "eof":
                temporary.unlink(missing_ok=True)
                return None
            duration = probe_duration(temporary)
            if duration <= 0:
                raise ValueError("Некорректная длительность TS-сегмента")
            os.replace(temporary, target)
            return number, target, duration
        except (requests.RequestException, subprocess.CalledProcessError, ValueError):
            temporary.unlink(missing_ok=True)
            if attempt == 2:
                raise RuntimeError(f"Не удалось загрузить аудиосегмент {number}")
            time.sleep(0.2 * (attempt + 1))
    raise RuntimeError(f"Не удалось загрузить аудиосегмент {number}")


def _fetch_segment(url: str, destination: Path) -> str:
    """Записывает ответ Kaltura; 404 обозначает конец последовательности."""
    with requests.get(
        url,
        headers={"User-Agent": "Mozilla/5.0", "Accept": "*/*"},
        stream=True,
        timeout=(10, 60),
    ) as response:
        if response.status_code == 404:
            return "eof"
        response.raise_for_status()
        size = 0
        with destination.open("wb") as output:
            for chunk in response.iter_content(65536):
                if chunk:
                    output.write(chunk)
                    size += len(chunk)
    if size < 1000:
        raise ValueError("Слишком маленький TS-сегмент")
    return "ok"


def _segment_url(base_url: str, number: int) -> str:
    """Собирает URL пронумерованного сегмента, сохраняя подпись HLS."""
    parsed = urlsplit(base_url)
    return urlunsplit(
        (
            parsed.scheme,
            parsed.netloc,
            f"{parsed.path.rstrip('/')}/seg-{number}-a1.ts",
            parsed.query,
            "",
        )
    )
