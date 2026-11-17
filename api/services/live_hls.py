"""Разбор плейлистов HLS для выбора аудиодорожки прямого эфира."""

import json
import re
import time
from urllib.parse import urljoin

import requests
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from downloader import VideoDownloader

PLAYER_HEADERS = {"User-Agent": "Mozilla/5.0"}


def resolve_live_audio_playlist(video_url: str, language: str = "eng") -> dict[str, str]:
    """Находит в плеере эфирный HLS URL выбранной аудиодорожки."""
    master_url = _discover_master_url(video_url)
    master = _fetch_playlist(master_url, video_url)
    rendition = select_audio_rendition(master, master_url, language)
    media = _fetch_playlist(rendition["url"], video_url)
    if classify_media_playlist(media) != "live":
        raise RuntimeError("Выбранный HLS-плейлист не является активным эфиром")
    return rendition


def _discover_master_url(video_url: str) -> str:
    """Открывает страницу Selenium и извлекает адрес master-плейлиста из запросов."""
    with VideoDownloader(headless=True) as downloader:
        driver = downloader.selenium.driver
        driver.get(video_url)
        heading = WebDriverWait(driver, 15).until(
            EC.element_to_be_clickable((By.TAG_NAME, "h1"))
        )
        heading.click()
        time.sleep(15)
        url = find_master_playlist_url(driver.get_log("performance"))
    if not url:
        raise RuntimeError("Не найден HLS master-плейлист прямого эфира")
    return url


def find_master_playlist_url(performance_log: list[dict]) -> str:
    """Возвращает URL HLS master-плейлиста из журнала запросов Chrome."""
    for entry in reversed(performance_log):
        url = _request_url(entry)
        path = url.split("?", 1)[0]
        if "/playManifest/" in path and path.endswith("/a.m3u8"):
            return url
    return ""


def _request_url(entry: dict) -> str:
    """Извлекает URL запроса Chrome, пропуская повреждённые записи лога."""
    try:
        event = json.loads(entry["message"])["message"]
        return event["params"]["request"]["url"]
    except (KeyError, TypeError, ValueError):
        return ""


def _fetch_playlist(url: str, referer: str) -> str:
    """Получает плейлист с реферером страницы, не раскрывая временный URL в ошибке."""
    try:
        response = requests.get(
            url,
            headers={**PLAYER_HEADERS, "Referer": referer},
            timeout=(10, 30),
        )
        if response.status_code != 200:
            raise RuntimeError(f"HLS-плейлист недоступен (HTTP {response.status_code})")
        return response.text
    except requests.RequestException as error:
        raise RuntimeError("Не удалось запросить HLS-плейлист") from error


def select_audio_rendition(
    master_playlist: str,
    master_url: str,
    language: str = "eng",
) -> dict[str, str]:
    """Выбирает аудиодорожку языка и возвращает её URL из master-плейлиста."""
    renditions = [
        _parse_attributes(line)
        for line in master_playlist.splitlines()
        if line.startswith("#EXT-X-MEDIA:") and "TYPE=AUDIO" in line
    ]
    selected = next(
        (item for item in renditions if item.get("LANGUAGE", "").lower() == language.lower()),
        None,
    )
    if not selected:
        raise RuntimeError(f"В HLS-плейлисте нет аудиодорожки языка {language}")
    uri = selected.get("URI")
    if not uri:
        raise RuntimeError(f"У аудиодорожки {language} отсутствует URI")
    return {
        "language": selected.get("LANGUAGE", ""),
        "name": selected.get("NAME", ""),
        "url": urljoin(master_url, uri),
    }


def classify_media_playlist(playlist: str) -> str:
    """Классифицирует медиа-плейлист как запись, эфир или неизвестный источник."""
    lines = {line.strip() for line in playlist.splitlines()}
    playlist_type = next(
        (line for line in lines if line.startswith("#EXT-X-PLAYLIST-TYPE:")),
        "",
    )
    if "#EXT-X-ENDLIST" in lines or playlist_type.endswith(":VOD"):
        return "recording"
    has_timeline = any(line.startswith("#EXT-X-TARGETDURATION:") for line in lines)
    has_segments = any(line.startswith("#EXTINF:") for line in lines)
    return "live" if has_timeline and has_segments else "unknown"


def _parse_attributes(line: str) -> dict[str, str]:
    """Разбирает атрибуты HLS-тега, сохраняя значения в кавычках."""
    payload = line.partition(":")[2]
    pattern = r'([A-Z0-9-]+)=("(?:[^"]*)"|[^,]*)'
    return {
        key: value.strip('"')
        for key, value in re.findall(pattern, payload)
    }
