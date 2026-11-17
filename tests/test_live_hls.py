import json
import unittest

from api.services.live_hls import (
    classify_media_playlist,
    find_master_playlist_url,
    select_audio_rendition,
)


class LiveHlsTests(unittest.TestCase):
    """Проверяет публичное распознавание HLS-плейлистов эфира."""

    def test_selects_requested_audio_rendition_from_master_playlist(self):
        """Выбирает русскую аудиодорожку и сохраняет временный query URL."""
        master = """
#EXTM3U
#EXT-X-MEDIA:TYPE=AUDIO,GROUP-ID="audio",LANGUAGE="eng",NAME="English",DEFAULT=YES,URI="index-s100.m3u8?token=secret"
#EXT-X-MEDIA:TYPE=AUDIO,GROUP-ID="audio",LANGUAGE="rus",NAME="Russian",DEFAULT=NO,URI="index-s108.m3u8?token=secret"
"""

        selected = select_audio_rendition(
            master,
            "https://cflive.kaltura.com/live/master.m3u8",
            language="rus",
        )

        self.assertEqual(selected["language"], "rus")
        self.assertEqual(
            selected["url"],
            "https://cflive.kaltura.com/live/index-s108.m3u8?token=secret",
        )

    def test_live_playlist_without_endlist_is_not_treated_as_recording(self):
        """Классифицирует скользящий список сегментов как live."""
        playlist = """
#EXTM3U
#EXT-X-TARGETDURATION:6
#EXT-X-MEDIA-SEQUENCE:216981993
#EXTINF:6.0,
seg-216981994-s108.ts
"""

        self.assertEqual(classify_media_playlist(playlist), "live")

    def test_completed_playlist_is_classified_as_recording(self):
        """Распознаёт завершённый HLS-список по ENDLIST."""
        playlist = """
#EXTM3U
#EXT-X-TARGETDURATION:6
#EXTINF:6.0,
seg-1.ts
#EXT-X-ENDLIST
"""

        self.assertEqual(classify_media_playlist(playlist), "recording")

    def test_incomplete_playlist_without_segment_metadata_is_unknown(self):
        """Не принимает пустой или повреждённый плейлист за эфир."""
        self.assertEqual(classify_media_playlist("#EXTM3U\n"), "unknown")

    def test_finds_master_playlist_without_logging_or_normalizing_its_token(self):
        """Извлекает только master URL, включая временный токен для запроса."""
        url = "https://kaltura.test/playManifest/entry/a.m3u8?token=secret"
        log = [
            {
                "message": json.dumps(
                    {
                        "message": {
                            "method": "Network.requestWillBeSent",
                            "params": {"request": {"url": url}},
                        }
                    }
                )
            }
        ]

        self.assertEqual(find_master_playlist_url(log), url)
