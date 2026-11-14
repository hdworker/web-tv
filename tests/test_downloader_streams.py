import unittest

from downloader import _stream_base_url


class HlsStreamSelectionTests(unittest.TestCase):
    def test_audio_only_selection_preserves_signed_query(self):
        """Проверяет извлечение аудиопотока с сохранением подписи."""
        url = (
            "https://cfvod.kaltura.com/scf/hls/p/2503451/seg-4-a1.ts"
            "?Policy=abc&Signature=xyz"
        )

        self.assertEqual(
            _stream_base_url(url, audio_only=True),
            "https://cfvod.kaltura.com/scf/hls/p/2503451?Policy=abc&Signature=xyz",
        )

    def test_audio_only_selection_skips_video_rendition(self):
        """Проверяет, что видеосегмент не выбран как аудио."""
        url = "https://cfvod.kaltura.com/scf/hls/p/2503451/seg-4-v1-a1.ts"

        self.assertIsNone(_stream_base_url(url, audio_only=True))


if __name__ == "__main__":
    unittest.main()
