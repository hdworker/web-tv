import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from api.services.caption_segmenter import SEGMENT_WINDOW, _download_window


class CaptionSegmenterTests(unittest.TestCase):
    """Проверки ограниченного параллельного окна HLS-сегментов."""

    @patch("api.services.caption_segmenter._download_segment")
    def test_download_window_uses_nine_workers_and_detects_end(self, download):
        """Проверяет окно из девяти сегментов и определение конца потока."""
        download.side_effect = lambda _base, number, _folder: (
            (number, Path(f"seg-{number}.ts"), 1.7) if number <= 6 else None
        )
        with tempfile.TemporaryDirectory() as folder:
            with ThreadPoolExecutor(max_workers=SEGMENT_WINDOW) as pool:
                segments, reached_end = _download_window(
                    pool,
                    "https://hls.test/base",
                    1,
                    Path(folder),
                )

        self.assertEqual(SEGMENT_WINDOW, 9)
        self.assertEqual([item[0] for item in segments], list(range(1, 7)))
        self.assertTrue(reached_end)
        self.assertEqual(download.call_count, 9)

    @patch("api.services.caption_segmenter._download_segment")
    def test_download_window_rejects_a_gap(self, download):
        """Проверяет, что сегменты после пропуска не сшиваются молча."""
        download.side_effect = lambda _base, number, _folder: (
            None if number == 3 else (number, Path(f"seg-{number}.ts"), 1.7)
        )
        with tempfile.TemporaryDirectory() as folder:
            with ThreadPoolExecutor(max_workers=SEGMENT_WINDOW) as pool:
                with self.assertRaisesRegex(RuntimeError, "пропуск"):
                    _download_window(pool, "https://hls.test/base", 1, Path(folder))


if __name__ == "__main__":
    unittest.main()
