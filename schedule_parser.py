import logging
import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Optional, Any
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)


@dataclass
class ScheduleItem:
    schedule_time: str = ""
    source_date: str = ""
    title: str = ""
    category: str = ""
    description: str = ""
    url: str = ""
    thumbnail: str = ""
    duration: str = ""


class ScheduleParser:
    BASE_URL = "https://webtv.un.org/en/schedule"
    
    def __init__(self):
        self._logging_enabled = True

    def enable_logging(self, enabled: bool) -> None:
        self._logging_enabled = enabled

    def _log(self, level: str, message: str) -> None:
        if self._logging_enabled:
            getattr(logger, level)(message)

    def _convert_to_iso_time(self, hours: str, minutes: str, ampm: str) -> str:
        try:
            hour = int(hours)
            minute = int(minutes)
            
            if ampm.lower() == "pm" and hour != 12:
                hour += 12
            elif ampm.lower() == "am" and hour == 12:
                hour = 0
            
            return f"{hour:02d}:{minute:02d}:00"
        except (ValueError, TypeError):
            return ""

    def _get_date_from_row(self, row) -> Optional[str]:
        timezone_div = row.find("div", class_="mediaun-timezone")
        if timezone_div:
            date_str = timezone_div.get("data-nid")
            return date_str
        
        time_div = row.find("div", class_="time")
        if time_div:
            date_single = time_div.find("span", class_="date-display-single")
            if date_single:
                return date_single.get("data-nid")
        return None

    def _extract_time(self, row) -> str:
        time_div = row.find("div", class_="time")
        if not time_div:
            return ""
        
        hours_elem = time_div.find("span", class_="date-display-single", attrs={"data-hours": True})
        minutes_elem = time_div.find("span", class_="date-display-single", attrs={"data-minutes": True})
        ampm_elem = time_div.find("span", class_="date-display-single", attrs={"data-int": True})
        
        hours = hours_elem.get("data-hours", "") if hours_elem else ""
        minutes = minutes_elem.get("data-minutes", "00") if minutes_elem else "00"
        ampm = ampm_elem.text.strip() if ampm_elem else "am"
        
        return self._convert_to_iso_time(hours, minutes, ampm)

    def _extract_category(self, row) -> str:
        category_elem = row.find("h6", class_="text-primary")
        return category_elem.text.strip() if category_elem else ""

    def _extract_title_and_url(self, row) -> tuple:
        title_div = row.find("div", class_="media-asset__title")
        if title_div:
            title_item = title_div.find("div", class_="field__item")
            title = title_item.text.strip() if title_item else ""
            
            link = title_div.find_parent("h4")
            if link:
                link_elem = link.find("a", href=True)
                if link_elem:
                    url = "https://webtv.un.org" + link_elem["href"]
                    return title, url
        return "", ""

    def _extract_description(self, row) -> str:
        desc_divs = row.find_all("div", class_=lambda x: x and "offset-sm-2" in x and "col-sm-10" in x)
        for div in desc_divs:
            text = div.text.strip()
            if text:
                return text
        return ""

    def _extract_thumbnail(self, row) -> str:
        img = row.find("img", class_="card-img")
        if img and img.get("src"):
            src = img["src"]
            if src.startswith("//"):
                src = "https:" + src
            return src
        return ""

    def _extract_duration(self, row) -> str:
        badge = row.find("span", class_="badge-dark")
        return badge.text.strip() if badge else ""

    def parse(self, date: str) -> List[Dict[str, Any]]:
        url = f"{self.BASE_URL}/{date}"
        return self.parse_url(url, source_date=date)

    def parse_url(self, url: str, source_date: str = "") -> List[Dict[str, Any]]:
        try:
            self._log("info", f"Загрузка страницы расписания: {url}")
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, "html.parser")
            
            items = []
            rows = soup.find_all("div", class_=lambda x: x and "un3-card-row-video" in x)
            
            self._log("info", f"Найдено {len(rows)} видео на странице")
            
            # дата страницы извлекается из URL
            date_from_url = url.rstrip("/").split("/")[-1]
            for row in rows:
                schedule_time = self._extract_time(row)
                category = self._extract_category(row)
                title, url = self._extract_title_and_url(row)
                description = self._extract_description(row)
                thumbnail = self._extract_thumbnail(row)
                duration = self._extract_duration(row)
                full_time = f"{date_from_url} {schedule_time}" if schedule_time else date_from_url
                if title:
                    item = ScheduleItem(
                        schedule_time=full_time,
                        source_date=source_date,
                        title=title,
                        category=category,
                        description=description,
                        url=url,
                        thumbnail=thumbnail,
                        duration=duration
                    )
                    items.append(asdict(item))
            
            return items
            
        except requests.exceptions.RequestException as e:
            self._log("error", f"Ошибка при загрузке страницы: {e}")
            return []

    def parse_period(self, start_date: str, end_date: str) -> List[Dict[str, Any]]:
        all_items: List[Dict[str, Any]] = []
        
        try:
            start = datetime.strptime(start_date, "%Y-%m-%d")
            end = datetime.strptime(end_date, "%Y-%m-%d")
        except ValueError as e:
            self._log("error", f"Неверный формат даты: {e}")
            return []
        
        current = start
        while current <= end:
            date_str = current.strftime("%Y-%m-%d")
            self._log("info", f"Парсинг даты: {date_str}")
            
            items = self.parse(date_str)
            # Группируем по дате: каждый день как отдельная группа с полем items
            group = {
                "date": date_str,
                "items": items,
            }
            all_items.append(group)
            
            current += timedelta(days=1)
        
        self._log("info", f"Всего найдено {len(all_items)} дня(ей) видео за период {start_date} - {end_date}")
        return all_items


def get_schedule(date: str) -> List[Dict[str, Any]]:
    parser = ScheduleParser()
    parser.enable_logging(False)
    return parser.parse(date)


def get_schedule_period(start_date: str, end_date: str) -> List[Dict[str, Any]]:
    parser = ScheduleParser()
    parser.enable_logging(False)
    return parser.parse_period(start_date, end_date)
