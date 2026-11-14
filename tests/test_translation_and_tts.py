import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.endpoints import caption_preparation, caption_tts
from api.services.caption_identity import cache_identity


def build_client() -> TestClient:
    """Создаёт приложение с обоими роутерами субтитров."""
    app = FastAPI()
    app.include_router(caption_preparation.router, prefix="/api/videos")
    app.include_router(caption_tts.router, prefix="/api/videos")
    return TestClient(app)


class TranslationSettingsTests(unittest.TestCase):
    """Проверки выбора движка перевода и его влияния на кеш."""

    def test_translation_target_changes_cache_key(self):
        """Перевод на другой язык должен давать отдельный ключ кеша."""
        url = "https://webtv.un.org/en/asset/id"

        original = cache_identity(url, "local")
        translated = cache_identity(url, "local", "ru", "opus")

        self.assertNotEqual(original["cache_key"], translated["cache_key"])
        self.assertEqual(translated["translate_to"], "ru")

    def test_translation_engine_changes_cache_key(self):
        """Смена движка перевода должна пересобирать транскрипт."""
        url = "https://webtv.un.org/en/asset/id"

        opus = cache_identity(url, "local", "ru", "opus")
        argos = cache_identity(url, "local", "ru", "argos")

        self.assertNotEqual(opus["cache_key"], argos["cache_key"])

    def test_engine_is_ignored_without_target(self):
        """Без языка перевода движок не должен дробить кеш."""
        url = "https://webtv.un.org/en/asset/id"

        first = cache_identity(url, "local", "", "opus")
        second = cache_identity(url, "local", "", "argos")

        self.assertEqual(first["cache_key"], second["cache_key"])

    def test_prepare_passes_translation_settings_to_job(self):
        """Проверяет, что параметры перевода доходят до постановки задачи."""
        client = build_client()
        with patch("api.endpoints.caption_preparation.CaptionRepository") as repository:
            with patch("api.endpoints.caption_preparation.start_job") as start_job:
                repository.return_value.get_cues.return_value = None
                repository.return_value.get_media.return_value = None
                start_job.return_value = {"job_id": "job-1", "status": "queued"}
                response = client.post(
                    "/api/videos/captions/prepare",
                    json={
                        "video_url": "https://webtv.un.org/en/asset/id",
                        "mode": "local",
                        "translate_to": "ru",
                        "translation_engine": "argos",
                    },
                )

        self.assertEqual(response.status_code, 202)
        identity = start_job.call_args.args[2]
        self.assertEqual(identity["translate_to"], "ru")
        self.assertEqual(identity["translation_engine"], "argos")


class TtsEndpointTests(unittest.TestCase):
    """Проверки выдачи голосов и mp3-озвучки."""

    def setUp(self):
        """Создаёт тестовый клиент."""
        self.client = build_client()

    @patch("api.endpoints.caption_tts.list_voices")
    def test_voices_are_filtered_by_language(self, voices):
        """Проверяет формат ответа со списком голосов."""
        voices.return_value = [{"name": "ru-RU-DmitryNeural", "locale": "ru-RU", "gender": "Male"}]
        response = self.client.get("/api/videos/captions/tts/voices?lang=ru")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["voices"][0]["name"], "ru-RU-DmitryNeural")
        voices.assert_called_once_with("ru")

    def test_voices_reject_bad_language(self):
        """Проверяет отказ для некорректного кода языка."""
        response = self.client.get("/api/videos/captions/tts/voices?lang=portuguese")

        self.assertEqual(response.status_code, 400)

    @patch("api.endpoints.caption_tts.synthesize")
    def test_audio_returns_mp3_file(self, synthesize):
        """Проверяет отдачу синтезированного mp3."""
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "voice.mp3"
            path.write_bytes(b"ID3test")
            synthesize.return_value = path
            response = self.client.get(
                "/api/videos/captions/tts/audio",
                params={"text": "Доброе утро", "voice": "ru-RU-DmitryNeural"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"ID3test")
        self.assertEqual(response.headers["content-type"], "audio/mpeg")

    @patch("api.endpoints.caption_tts.synthesize")
    def test_audio_reports_unavailable_service(self, synthesize):
        """Проверяет понятную ошибку, если Edge TTS недоступен."""
        synthesize.side_effect = RuntimeError("403")
        response = self.client.get(
            "/api/videos/captions/tts/audio",
            params={"text": "Hello", "voice": "en-US-AriaNeural"},
        )

        self.assertEqual(response.status_code, 502)


if __name__ == "__main__":
    unittest.main()
