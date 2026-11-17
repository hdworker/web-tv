import os
import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import Mock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.endpoints.caption_preparation import router
from api.services.caption_asr import to_cues, transcribe_cloud


class CaptionPreparationTests(unittest.TestCase):
    def setUp(self):
        """Создаёт тестовый HTTP-клиент API подготовки субтитров."""
        app = FastAPI()
        app.include_router(router, prefix="/api/videos")
        self.client = TestClient(app)

    def test_prepare_starts_job_for_un_video(self):
        """Проверяет постановку страницы UN Web TV в очередь."""
        with patch(
            "api.endpoints.caption_preparation.CaptionRepository"
        ) as repository_factory:
            with patch("api.endpoints.caption_preparation.start_job") as start_job:
                repository_factory.return_value.get_cues.return_value = None
                start_job.return_value = {"job_id": "abc123", "status": "queued"}
                response = self.client.post(
                    "/api/videos/captions/prepare",
                    json={
                        "video_url": "https://webtv.un.org/en/asset/k19/k19kdi9mh4",
                        "mode": "local",
                    },
                )

        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.json()["job_id"], "abc123")
        start_job.assert_called_once()

    def test_prepare_passes_explicit_live_mode_to_job(self):
        """Проверяет передачу режима эфира при установленной галочке."""
        with patch(
            "api.endpoints.caption_preparation.CaptionRepository"
        ) as repository_factory:
            with patch("api.endpoints.caption_preparation.start_job") as start_job:
                repository_factory.return_value.get_cues.return_value = None
                start_job.return_value = {"job_id": "live-1", "status": "queued"}
                response = self.client.post(
                    "/api/videos/captions/prepare",
                    json={
                        "video_url": "https://webtv.un.org/en/asset/k13/k13tn4gno5",
                        "mode": "local",
                        "live_stream": True,
                    },
                )

        self.assertEqual(response.status_code, 202)
        self.assertTrue(start_job.call_args.kwargs["live_stream"])

    def test_stop_route_requests_live_job_shutdown(self):
        """Проверяет API-команду остановки активного эфира."""
        with patch("api.endpoints.caption_preparation.stop_job", return_value=True):
            response = self.client.post("/api/videos/captions/jobs/live-1/stop")

        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.json()["status"], "stopping")

    def test_prepare_rejects_non_un_domain(self):
        """Проверяет запрет URL за пределами UN Web TV."""
        response = self.client.post(
            "/api/videos/captions/prepare",
            json={"video_url": "https://example.org/en/asset/video"},
        )

        self.assertEqual(response.status_code, 400)

    def test_prepare_returns_persisted_cache(self):
        """Проверяет мгновенный возврат ранее сохранённых таймкодов."""
        with tempfile.TemporaryDirectory() as folder:
            audio_path = Path(folder) / "archive.flac"
            audio_path.write_bytes(b"fLaC")
            with patch(
                "api.endpoints.caption_preparation.CaptionRepository"
            ) as repository_factory:
                with patch("api.endpoints.caption_preparation.start_job") as start_job:
                    repository_factory.return_value.get_cues.return_value = {
                        "cues": [{"start": 0, "end": 1, "text": "Cached."}],
                        "is_complete": True,
                    }
                    repository_factory.return_value.get_media.return_value = {
                        "audio_path": str(audio_path)
                    }
                    response = self.client.post(
                        "/api/videos/captions/prepare",
                        json={
                            "video_url": "https://webtv.un.org/en/asset/id",
                            "mode": "local",
                        },
                    )
                    start_job.assert_not_called()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["cached"])
        self.assertEqual(response.json()["cues"][0]["text"], "Cached.")

    def test_partial_cache_starts_or_resumes_a_job(self):
        """Проверяет, что частичные cues не выдают за полный транскрипт."""
        with tempfile.TemporaryDirectory() as folder:
            audio_path = Path(folder) / "archive.flac"
            audio_path.write_bytes(b"fLaC")
            with patch(
                "api.endpoints.caption_preparation.CaptionRepository"
            ) as repository_factory:
                with patch("api.endpoints.caption_preparation.start_job") as start_job:
                    repository_factory.return_value.get_cues.return_value = {
                        "cues": [{"start": 0, "end": 1, "text": "Partial."}],
                        "is_complete": False,
                    }
                    repository_factory.return_value.get_media.return_value = {
                        "audio_path": str(audio_path)
                    }
                    start_job.return_value = {"job_id": "retry-1", "status": "queued"}
                    response = self.client.post(
                        "/api/videos/captions/prepare",
                        json={
                            "video_url": "https://webtv.un.org/en/asset/id",
                            "mode": "local",
                        },
                    )

        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.json()["job_id"], "retry-1")
        start_job.assert_called_once()

    def test_media_route_serves_flac_archive(self):
        """Проверяет получение сохранённого FLAC по asset key."""
        with tempfile.TemporaryDirectory() as folder:
            audio_path = Path(folder) / "speech.flac"
            audio_path.write_bytes(b"fLaCtest")
            with patch(
                "api.endpoints.caption_preparation.CaptionRepository"
            ) as repository_factory:
                repository_factory.return_value.get_media.return_value = {
                    "audio_path": str(audio_path)
                }
                response = self.client.get(
                    f"/api/videos/captions/media/{'a' * 64}"
                )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, b"fLaCtest")
        self.assertEqual(response.headers["content-type"], "audio/flac")

    def test_asr_segments_are_normalized_to_cues(self):
        """Проверяет привязку локальных таймкодов к общему таймлайну."""
        cues = to_cues(
            [{"start": 1.2, "end": 2.7, "text": " Hello "}, {"start": 3, "end": 3, "text": ""}],
            offset=120,
        )

        self.assertEqual(cues, [{"start": 121.2, "end": 122.7, "text": "Hello"}])

    @patch("api.services.caption_asr.requests.post")
    def test_cloud_chunks_keep_absolute_timestamps(self, post):
        """Проверяет смещение таймкодов облачных частей относительно всей записи."""
        response = Mock()
        response.json.return_value = {
            "segments": [{"start": 0.5, "end": 1.5, "text": " spoken phrase "}]
        }
        post.return_value = response
        with tempfile.TemporaryDirectory() as folder:
            audio_path = Path(folder) / "audio.wav"
            with wave.open(str(audio_path), "wb") as audio:
                audio.setnchannels(1)
                audio.setsampwidth(2)
                audio.setframerate(16000)
                audio.writeframes(b"\x00\x00" * 16000 * 121)
            with patch.dict(
                os.environ,
                {"OPENAI_API_KEY": "test-key", "OPENAI_URL": "https://asr.test/v1"},
            ):
                cues = transcribe_cloud(audio_path, lambda _message, _progress: None)

        self.assertEqual(len(cues), 2)
        self.assertEqual(cues[0]["start"], 0.5)
        self.assertEqual(cues[1]["start"], 120.5)
        self.assertEqual(post.call_count, 2)

    @patch("api.endpoints.caption_preparation.get_job")
    def test_websocket_sends_terminal_job_update(self, get_job):
        """Проверяет получение завершённой задачи по WebSocket."""
        get_job.return_value = {
            "job_id": "job-1",
            "status": "complete",
            "progress": 100,
            "message": "Субтитры готовы",
            "cache_key": "cache-1",
            "version": 1,
        }
        with patch("api.endpoints.caption_preparation.CaptionRepository") as repository:
            repository.return_value.get_cues.return_value = {
                "cues": [{"start": 0, "end": 1, "text": "Hello."}]
            }
            with self.client.websocket_connect(
                "/api/videos/captions/jobs/job-1/ws"
            ) as websocket:
                event = websocket.receive_json()

        self.assertEqual(event["type"], "update")
        self.assertEqual(event["job"]["status"], "complete")

    @patch("api.endpoints.caption_preparation.get_job")
    def test_websocket_delivers_partial_cues_before_completion(self, get_job):
        """Проверяет отправку первого готового блока до конца записи."""
        get_job.return_value = {
            "job_id": "job-partial",
            "status": "partial",
            "progress": None,
            "message": "Готово блоков: 1",
            "cues": [{"start": 0, "end": 1, "text": "Early caption."}],
            "blocks_done": 1,
            "version": 1,
        }
        with self.client.websocket_connect(
            "/api/videos/captions/jobs/job-partial/ws"
        ) as websocket:
            event = websocket.receive_json()

        self.assertEqual(event["type"], "partial")
        self.assertEqual(event["job"]["cues"][0]["text"], "Early caption.")
if __name__ == "__main__":
    unittest.main()
