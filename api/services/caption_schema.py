"""Схема SQLite-таблиц архива аудио и кеша субтитров."""

import sqlite3


def create_caption_tables(connection: sqlite3.Connection) -> None:
    """Создаёт таблицы caption_media и caption_caches с миграцией флага."""
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS caption_media (
            asset_key TEXT PRIMARY KEY,
            video_url TEXT NOT NULL,
            audio_path TEXT NOT NULL,
            audio_format TEXT NOT NULL DEFAULT 'flac',
            duration_seconds REAL,
            file_size_bytes INTEGER NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS caption_caches (
            cache_key TEXT PRIMARY KEY,
            asset_key TEXT NOT NULL,
            mode TEXT NOT NULL,
            model TEXT NOT NULL,
            language TEXT NOT NULL,
            cues_json TEXT NOT NULL,
            is_complete INTEGER NOT NULL DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(asset_key) REFERENCES caption_media(asset_key)
        )
        """
    )
    columns = {
        row["name"]
        for row in connection.execute("PRAGMA table_info(caption_caches)")
    }
    if "is_complete" not in columns:
        connection.execute(
            "ALTER TABLE caption_caches "
            "ADD COLUMN is_complete INTEGER NOT NULL DEFAULT 1"
        )
