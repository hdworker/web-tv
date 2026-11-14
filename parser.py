import logging
import requests
from bs4 import BeautifulSoup
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, field, asdict
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class VideoMetadata:
    title: str = ""
    description: str = ""
    url: str = ""
    broadcasting_entity: str = ""
    original_languages: str = ""
    production_date: str = ""
    video_length: str = ""
    categories: str = ""
    transcript: str = ""


class VideoPageParser:
    def __init__(self):
        self._logging_enabled = True

    def enable_logging(self, enabled: bool) -> None:
        self._logging_enabled = enabled

    def _log(self, level: str, message: str) -> None:
        if self._logging_enabled:
            getattr(logger, level)(message)

    def parse(self, url: str, html: Optional[str] = None) -> VideoMetadata:
        if html is None:
            html = self._fetch_html(url)
        
        if not html:
            return VideoMetadata(url=url)
        
        soup = BeautifulSoup(html, 'html.parser')
        
        return VideoMetadata(
            title=self._extract_title(soup),
            description=self._extract_description(soup),
            url=url,
            broadcasting_entity=self._extract_broadcasting_entity(soup),
            original_languages=self._extract_languages(soup),
            production_date=self._extract_production_date(soup),
            video_length=self._extract_video_length(soup),
            categories=self._extract_categories(soup),
            transcript=self._extract_transcript(soup)
        )

    def _fetch_html(self, url: str) -> Optional[str]:
        try:
            self._log("info", f"Загрузка страницы: {url}")
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            return response.text
        except requests.exceptions.RequestException as e:
            self._log("error", f"Ошибка при загрузке страницы: {e}")
            return None

    def _extract_title(self, soup: BeautifulSoup) -> str:
        title_div = soup.find('h2', class_='field__item')
        if title_div:
            return title_div.text.strip()
        
        title_tag = soup.find('h1')
        if title_tag:
            return title_tag.text.strip()
        
        return ""

    def _extract_description(self, soup: BeautifulSoup) -> str:
        description_div = soup.find('div', class_='smt-content')
        return description_div.text.strip() if description_div else ""

    def _extract_broadcasting_entity(self, soup: BeautifulSoup) -> str:
        link = soup.find('a', href=lambda href: href and "un_entity" in href)
        return link.get_text(strip=True) if link else ""

    def _extract_languages(self, soup: BeautifulSoup) -> str:
        languages_div = soup.find('div', class_='field--name-field-asset-language')
        if languages_div:
            languages = [a_tag.text.strip() for a_tag in languages_div.find_all('a')]
            return ", ".join(languages)
        return ""

    def _extract_production_date(self, soup: BeautifulSoup) -> str:
        production_date_div = soup.find('div', class_='field--name-field-production-date')
        if production_date_div:
            time_tag = production_date_div.find('time')
            if time_tag:
                return time_tag.text.strip()
        return ""

    def _extract_video_length(self, soup: BeautifulSoup) -> str:
        duration_div = soup.find('div', class_='field--name-field-duration')
        if duration_div:
            duration_item = duration_div.find('div', class_='field__item')
            if duration_item:
                return duration_item.text.strip()
        return ""

    def _extract_categories(self, soup: BeautifulSoup) -> str:
        categories_divs = soup.find_all('div', class_='field--name-field-categories')
        if len(categories_divs) >= 2:
            categories_div = categories_divs[1]
            categories_item = categories_div.find('div', class_='field__item')
            if categories_item:
                a_tags = categories_item.find_all('a')
                if a_tags:
                    return " / ".join(a_tag.text.strip() for a_tag in a_tags)
                else:
                    return categories_item.text.strip()
        return ""

    def _extract_transcript(self, soup: BeautifulSoup) -> str:
        root = soup.find('div', class_=lambda x: x and 'transcript__root' in x)
        if not root:
            return ""
        
        captions = root.find_all('div', class_=lambda x: x and 'caption__caption' in x)
        
        result = []
        for cap in captions:
            time_elem = cap.find('div', class_=lambda x: x and 'caption__caption-time' in x)
            text_elem = cap.find('span')
            
            timestamp = time_elem.text.strip() if time_elem else ""
            text = text_elem.text.strip() if text_elem else ""
            
            if text:
                result.append(f"[{timestamp}] {text}")
        
        self._log("info", f"Найдено {len(result)} фрагментов транскрипта")
        return "\n".join(result)


class SchedulePageParser:
    def __init__(self):
        self._logging_enabled = True

    def enable_logging(self, enabled: bool) -> None:
        self._logging_enabled = enabled

    def _log(self, level: str, message: str) -> None:
        if self._logging_enabled:
            getattr(logger, level)(message)

    def parse(self, url: str) -> List[str]:
        try:
            self._log("info", f"Загрузка страницы расписания: {url}")
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            video_links = []
            
            for a in soup.find_all('a', href=True):
                title_div = a.find('div', class_='field__item')
                if title_div and 'media-asset__title' in str(a):
                    full_url = "https://webtv.un.org" + a['href']
                    video_links.append(full_url)
            
            self._log("info", f"Найдено ссылок на видео: {len(video_links)}")
            return video_links
            
        except requests.exceptions.RequestException as e:
            self._log("error", f"Ошибка при загрузке страницы: {e}")
            return []


def parse_video_page(url: str) -> Dict[str, Any]:
    parser = VideoPageParser()
    metadata = parser.parse(url)
    return asdict(metadata)


def parse_schedule_page(date: str) -> List[str]:
    url = f"https://webtv.un.org/en/schedule/{date}"
    parser = SchedulePageParser()
    return parser.parse(url)
