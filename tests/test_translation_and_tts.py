import asyncio
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.endpoints import caption_preparation, caption_tts
from api.services.caption_identity import cache_identity
from api.services import tts_edge


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

    def test_live_capture_uses_a_separate_cache_key(self):
        """Не смешивает результаты прямого эфира с записью того же URL."""
        url = "https://webtv.un.org/en/asset/id"

        recording = cache_identity(url, "local")
        live = cache_identity(url, "local", live_stream=True)

        self.assertNotEqual(recording["cache_key"], live["cache_key"])

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
                params={
                    "text": "Доброе утро",
                    "voice": "ru-RU-DmitryNeural",
                    "rate": 10,
                    "pitch": -5,
                    "volume": 20,
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"ID3test")
        self.assertEqual(response.headers["content-type"], "audio/mpeg")
        synthesize.assert_called_once_with(
            "Доброе утро",
            "ru-RU-DmitryNeural",
            rate=10,
            pitch=-5,
            volume=20,
        )

    def test_audio_rejects_edge_values_outside_supported_ranges(self):
        """Ограничивает параметры Edge TTS безопасными диапазонами."""
        response = self.client.get(
            "/api/videos/captions/tts/audio",
            params={"text": "Hello", "voice": "en-US-AriaNeural", "rate": 75},
        )

        self.assertEqual(response.status_code, 422)

    @patch("api.endpoints.caption_tts.synthesize")
    def test_audio_reports_unavailable_service(self, synthesize):
        """Проверяет понятную ошибку, если Edge TTS недоступен."""
        synthesize.side_effect = RuntimeError("403")
        response = self.client.get(
            "/api/videos/captions/tts/audio",
            params={"text": "Hello", "voice": "en-US-AriaNeural"},
        )

        self.assertEqual(response.status_code, 502)


class EdgeTtsParameterTests(unittest.TestCase):
    """Проверки передачи настроек в библиотеку Edge TTS."""

    def test_stream_uses_requested_rate_pitch_and_volume(self):
        """Преобразует числовые настройки в формат Edge TTS."""
        received = {}

        class FakeCommunicate:
            """Подмена сетевого клиента Edge TTS для изолированного теста."""

            def __init__(self, text, voice, **options):
                received.update(text=text, voice=voice, **options)

            async def stream(self):
                yield {"type": "audio", "data": b"x" * 512}

        fake_module = SimpleNamespace(Communicate=FakeCommunicate)
        with patch.dict("sys.modules", {"edge_tts": fake_module}):
            audio = asyncio.run(
                tts_edge._stream_audio(
                    "Hello",
                    "en-US-AriaNeural",
                    rate=10,
                    pitch=-5,
                    volume=20,
                )
            )

        self.assertEqual(len(audio), 512)
        self.assertEqual(
            received,
            {
                "text": "Hello",
                "voice": "en-US-AriaNeural",
                "rate": "+10%",
                "pitch": "-5Hz",
                "volume": "+20%",
            },
        )

    def test_cache_separates_audio_settings(self):
        """Не возвращает аудио из кеша с другими параметрами речи."""
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(tts_edge, "CACHE_DIR", Path(folder)):
                with patch.object(
                    tts_edge,
                    "_synthesize_with_fallback",
                    return_value=b"x" * 600,
                ) as synthesize:
                    normal = tts_edge.synthesize("Hello", "en-US-AriaNeural")
                    faster = tts_edge.synthesize(
                        "Hello", "en-US-AriaNeural", rate=10
                    )
                    repeated = tts_edge.synthesize("Hello", "en-US-AriaNeural")

        self.assertNotEqual(normal, faster)
        self.assertEqual(normal, repeated)
        self.assertEqual(synthesize.call_count, 2)

if __name__ == "__main__":
    unittest.main()
