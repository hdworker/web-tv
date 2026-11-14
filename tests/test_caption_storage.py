import sqlite3
import tempfile
import unittest
from pathlib import Path

from api.services.caption_identity import cache_identity
from api.services.caption_repository import CaptionRepository


class CaptionStorageTests(unittest.TestCase):
    """Проверки долгосрочного хранения медиа и таймкодов."""

    def test_audio_and_cues_survive_database_reopen(self):
        """Проверяет сохранение FLAC-метаданных и субтитров между соединениями."""
        with tempfile.TemporaryDirectory() as folder:
            db_path = str(Path(folder) / "captions.sqlite3")
            first = CaptionRepository(db_path)
            identity = cache_identity("https://webtv.un.org/en/asset/id?utm=ignored", "local")
            cues = [{"start": 1.0, "end": 2.0, "text": "Hello."}]
            first.save_media(
                identity["asset_key"],
                identity["canonical_url"],
                "video/captions/audio.flac",
                12.5,
                4096,
            )
            first.save_cues(
                identity["cache_key"],
                identity["asset_key"],
                "local",
                identity["model"],
                "en",
                cues,
            )

            reopened = CaptionRepository(db_path)

            self.assertEqual(
                reopened.get_media(identity["asset_key"])["audio_format"],
                "flac",
            )
            self.assertEqual(
                reopened.get_cues(identity["cache_key"])["cues"],
                cues,
            )
            self.assertTrue(reopened.get_cues(identity["cache_key"])["is_complete"])

    def test_partial_cues_are_persisted_as_incomplete(self):
        """Проверяет, что частичный результат нельзя принять за готовый кеш."""
        with tempfile.TemporaryDirectory() as folder:
            repository = CaptionRepository(str(Path(folder) / "partial.sqlite3"))
            repository.save_media(
                "asset",
                "https://webtv.un.org/en/asset/id",
                "audio.flac",
                3,
                10,
            )
            repository.save_cues(
                "cache",
                "asset",
                "local",
                "small",
                "en",
                [{"start": 0, "end": 1, "text": "Partial"}],
                is_complete=False,
            )

            result = repository.get_cues("cache")

        self.assertFalse(result["is_complete"])
        self.assertEqual(result["cues"][0]["text"], "Partial")

    def test_cache_key_varies_by_recognition_mode(self):
        """Проверяет разделение результатов разных ASR-режимов."""
        url = "https://webtv.un.org/en/asset/id"

        self.assertNotEqual(
            cache_identity(url, "local")["cache_key"],
            cache_identity(url, "cloud")["cache_key"],
        )

    def test_asset_identity_ignores_tracking_query(self):
        """Проверяет, что параметры ссылки не создают дубликат аудиоархива."""
        first = cache_identity("https://webtv.un.org/en/asset/id?utm_source=a", "local")
        second = cache_identity("https://webtv.un.org/en/asset/id#player", "local")

        self.assertEqual(first["asset_key"], second["asset_key"])

    def test_repository_adds_completion_flag_to_existing_cache_table(self):
        """Проверяет миграцию кеша, созданного предыдущей версией приложения."""
        with tempfile.TemporaryDirectory() as folder:
            db_path = str(Path(folder) / "old.sqlite3")
            connection = sqlite3.connect(db_path)
            connection.execute(
                """
                CREATE TABLE caption_caches (
                    cache_key TEXT PRIMARY KEY,
                    asset_key TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    model TEXT NOT NULL,
                    language TEXT NOT NULL,
                    cues_json TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            connection.commit()
            connection.close()

            repository = CaptionRepository(db_path)
            check = sqlite3.connect(db_path)
            columns = check.execute("PRAGMA table_info(caption_caches)").fetchall()
            check.close()

        self.assertIn("is_complete", [column[1] for column in columns])


if __name__ == "__main__":
    unittest.main()
