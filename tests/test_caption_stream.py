import unittest
from pathlib import Path
from unittest.mock import patch

from api.services.caption_segmenter import AudioSegment
from api.services.caption_stream import download_and_transcribe


class CaptionStreamTests(unittest.TestCase):
    """Проверки параллельной загрузки и последовательного ASR-конвейера."""

    @patch("api.services.caption_stream_producer.archive_segments")
    @patch("api.services.caption_stream.transcribe_local")
    @patch("api.services.caption_stream.load_local_model")
    @patch("api.services.caption_stream.VideoTranscriber.extract_audio", return_value=True)
    @patch("api.services.caption_stream.concatenate_segments")
    @patch("api.services.caption_stream_producer.download_segments")
    def test_asr_consumes_audio_batches_and_waits_for_archive(
        self,
        download,
        concatenate,
        _extract_audio,
        load_model,
        transcribe,
        archive,
    ):
        """Проверяет два ASR-блока и создание архива в одном конвейере."""
        download.return_value = iter(
            [
                AudioSegment(1, Path("seg-1.ts"), 60, 0),
                AudioSegment(2, Path("seg-2.ts"), 60, 60),
                AudioSegment(3, Path("seg-3.ts"), 30, 120),
            ]
        )
        concatenate.side_effect = [Path("batch-1.ts"), Path("batch-2.ts")]
        transcribe.side_effect = [
            [{"start": 1.0, "end": 2.0, "text": "First."}],
            [{"start": 121.0, "end": 122.0, "text": "Second."}],
        ]
        partials = []

        cues = download_and_transcribe(
            "https://webtv.un.org/en/asset/id",
            "local",
            "asset-key",
            lambda _message, _progress: None,
            lambda number, batch: partials.append((number, batch)),
        )

        self.assertEqual([cue["text"] for cue in cues], ["First.", "Second."])
        self.assertEqual([item[0] for item in partials], [1, 2])
        self.assertEqual(transcribe.call_count, 2)
        archive.assert_called_once()
        load_model.assert_called_once()


if __name__ == "__main__":
    unittest.main()
