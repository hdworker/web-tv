import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.endpoints.live_transcription import router


class LiveTranscriptionTests(unittest.TestCase):
    def setUp(self):
        """Создаёт тестовый клиент для проверки API распознавания."""
        app = FastAPI()
        app.include_router(router, prefix="/api/videos")
        self.client = TestClient(app)

    def test_health_reports_cloud_key_requirement(self):
        """Проверяет предупреждение о незаданном облачном ключе."""
        with patch.dict("os.environ", {}, clear=True):
            response = self.client.get(
                "/api/videos/live-transcription/health?mode=cloud"
            )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["ready"])

    def test_chunk_returns_transcribed_text(self):
        """Проверяет ответ с текстом для корректного WAV."""
        wav = b"RIFF" + b"\x00" * 4 + b"WAVE" + b"\x00" * 32
        with patch(
            "api.endpoints.live_transcription._transcribe",
            return_value="Hello world.",
        ) as transcribe:
            response = self.client.post(
                "/api/videos/live-transcription/chunk?mode=local",
                content=wav,
                headers={"content-type": "audio/wav"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["text"], "Hello world.")
        transcribe.assert_called_once()

    def test_chunk_rejects_non_wav_payload(self):
        """Проверяет отказ для тела, не являющегося WAV."""
        response = self.client.post(
            "/api/videos/live-transcription/chunk?mode=local",
            content=b"not audio",
        )

        self.assertEqual(response.status_code, 415)

    def test_chunk_rejects_unknown_mode(self):
        """Проверяет валидацию режима распознавания."""
        wav = b"RIFF" + b"\x00" * 4 + b"WAVE" + b"\x00" * 32
        response = self.client.post(
            "/api/videos/live-transcription/chunk?mode=unsupported",
            content=wav,
        )

        self.assertEqual(response.status_code, 400)


if __name__ == "__main__":
    unittest.main()
