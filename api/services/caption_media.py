"""Постоянное архивирование FLAC и временная склейка сегментов."""

import os
import subprocess
from pathlib import Path
from typing import Callable

from api.services.caption_ffmpeg import encode_lossless_flac, probe_duration
from api.services.caption_repository import CaptionRepository

Progress = Callable[[str, int | None], None]


def get_saved_audio(asset_key: str) -> Path | None:
    """Возвращает существующий FLAC-архив для записи."""
    media = CaptionRepository().get_media(asset_key)
    if media and Path(media["audio_path"]).is_file():
        return Path(media["audio_path"])
    return None


def concatenate_segments(
    segments: list[Path],
    workdir: Path,
    output_name: str,
) -> Path:
    """Склеивает заданный набор TS-сегментов во временный файл."""
    output_path = workdir / output_name
    file_list = workdir / f"{output_name}.txt"
    file_list.write_text(
        "".join(f"file '{segment.as_posix()}'\n" for segment in segments),
        encoding="utf-8",
    )
    subprocess.run(
        [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "concat",
            "-safe", "0", "-i", str(file_list), "-c", "copy", str(output_path),
        ],
        check=True,
        timeout=1800,
    )
    return output_path


def archive_segments(
    video_url: str,
    asset_key: str,
    segments: list[Path],
    workdir: Path,
    progress: Progress,
) -> Path:
    """Склеивает все сегменты, сохраняет FLAC и записывает метаданные."""
    recording = concatenate_segments(segments, workdir, "recording.ts")
    temporary_flac = workdir / "archive.flac"
    encode_lossless_flac(recording, temporary_flac)
    duration = probe_duration(temporary_flac)
    audio_dir = Path("video") / "captions"
    audio_dir.mkdir(parents=True, exist_ok=True)
    audio_path = audio_dir / f"{asset_key}.flac"
    progress("Сохраняю FLAC-архив аудиодорожки", 70)
    os.replace(temporary_flac, audio_path)
    CaptionRepository().save_media(
        asset_key,
        video_url,
        str(audio_path),
        duration,
        audio_path.stat().st_size,
    )
    return audio_path
