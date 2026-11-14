"""SQLite-хранилище FLAC-архивов и таймкодированных субтитров."""

import json
import sqlite3
from contextlib import contextmanager
from typing import Any, Iterator

from api.services.caption_schema import create_caption_tables


class CaptionRepository:
    """Читает и сохраняет долговечные данные субтитров."""

    def __init__(self, db_path: str = "un_videos.db"):
        self.db_path = db_path
        self._initialize()

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        """Открывает SQLite-соединение и гарантирует commit/close."""
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def _initialize(self) -> None:
        """Создаёт таблицы архива и кеша при первом использовании."""
        with self._connection() as connection:
            create_caption_tables(connection)

    def get_media(self, asset_key: str) -> dict[str, Any] | None:
        """Возвращает свойства сохранённого аудиоархива."""
        with self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM caption_media WHERE asset_key = ?",
                (asset_key,),
            ).fetchone()
        return dict(row) if row else None

    def save_media(
        self,
        asset_key: str,
        video_url: str,
        audio_path: str,
        duration_seconds: float,
        file_size_bytes: int,
    ) -> None:
        """Сохраняет метаданные FLAC-архива для asset."""
        with self._connection() as connection:
            connection.execute(
                """
                INSERT INTO caption_media (
                    asset_key, video_url, audio_path, audio_format,
                    duration_seconds, file_size_bytes
                ) VALUES (?, ?, ?, 'flac', ?, ?)
                ON CONFLICT(asset_key) DO UPDATE SET
                    video_url = excluded.video_url,
                    audio_path = excluded.audio_path,
                    audio_format = excluded.audio_format,
                    duration_seconds = excluded.duration_seconds,
                    file_size_bytes = excluded.file_size_bytes,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (asset_key, video_url, audio_path, duration_seconds, file_size_bytes),
            )

    def get_cues(self, cache_key: str) -> dict[str, Any] | None:
        """Возвращает кеш субтитров и метаданные распознавания."""
        with self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM caption_caches WHERE cache_key = ?",
                (cache_key,),
            ).fetchone()
        if not row:
            return None
        result = dict(row)
        result["cues"] = json.loads(result.pop("cues_json"))
        result["is_complete"] = bool(result["is_complete"])
        return result

    def save_cues(
        self,
        cache_key: str,
        asset_key: str,
        mode: str,
        model: str,
        language: str,
        cues: list[dict],
        is_complete: bool = True,
    ) -> None:
        """Сохраняет таймкодированные фразы без срока удаления."""
        cues_json = json.dumps(cues, ensure_ascii=False, separators=(",", ":"))
        with self._connection() as connection:
            connection.execute(
                """
                INSERT INTO caption_caches (
                    cache_key, asset_key, mode, model, language, cues_json, is_complete
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(cache_key) DO UPDATE SET
                    cues_json = excluded.cues_json,
                    is_complete = excluded.is_complete,
                    created_at = CURRENT_TIMESTAMP
                """,
                (
                    cache_key,
                    asset_key,
                    mode,
                    model,
                    language,
                    cues_json,
                    int(is_complete),
                ),
            )
