"""Утилиты ffmpeg для архивации и метаданных аудио."""

import subprocess
from pathlib import Path


def encode_lossless_flac(media_path: Path, output_path: Path) -> None:
    """Кодирует аудиодорожку без потерь в FLAC."""
    subprocess.run(
        [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-i", str(media_path), "-map", "0:a:0", "-vn",
            "-c:a", "flac", "-compression_level", "8", "-f", "flac",
            str(output_path),
        ],
        check=True,
        timeout=1800,
    )


def probe_duration(media_path: Path) -> float:
    """Возвращает длительность FLAC-файла в секундах."""
    result = subprocess.run(
        [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", str(media_path),
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    return float(result.stdout.strip())


def split_wav_chunks(audio_path: Path, workdir: Path) -> list[Path]:
    """Готовит двухминутные временные WAV-блоки для повторного ASR."""
    pattern = workdir / "asr-%04d.wav"
    subprocess.run(
        [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
            "-i", str(audio_path), "-vn", "-acodec", "pcm_s16le",
            "-ar", "16000", "-ac", "1", "-f", "segment",
            "-segment_time", "120", "-reset_timestamps", "1",
            "-segment_format", "wav", str(pattern),
        ],
        check=True,
        timeout=3600,
    )
    chunks = sorted(workdir.glob("asr-*.wav"))
    if not chunks:
        raise RuntimeError("ffmpeg не создал WAV-блоки")
    return chunks
