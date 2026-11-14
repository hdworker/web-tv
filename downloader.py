import logging
import re
import os
import subprocess
import time
from pathlib import Path
from typing import Optional, Tuple, List

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

try:
    from chromedriver_py import binary_path
except ImportError:
    binary_path = None

try:
    import chromedriver_autoinstaller
    CHROMEDRIVER_AVAILABLE = True
except ImportError:
    CHROMEDRIVER_AVAILABLE = False

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)


def natural_sort_key(s: str) -> List:
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r'([0-9]+)', s)]


class SeleniumDownloader:
    def __init__(self, headless: bool = False, driver_path: Optional[str] = None):
        self.driver = self._init_driver(headless, driver_path)

    def _init_driver(self, headless: bool, driver_path: Optional[str]) -> webdriver.Chrome:
        chrome_options = Options()
        if headless:
            chrome_options.add_argument("--headless")
            chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--log-level=3")
        chrome_options.add_argument("--mute-audio")
        chrome_options.set_capability("goog:loggingPrefs", {"performance": "ALL"})

        if driver_path:
            from selenium.webdriver.chrome.service import Service
            service = Service(driver_path)
            driver = webdriver.Chrome(service=service, options=chrome_options)
        else:
            if CHROMEDRIVER_AVAILABLE:
                import chromedriver_autoinstaller
                chromedriver_autoinstaller.install()
            driver = webdriver.Chrome(options=chrome_options)

        logger.info("Инициализация драйвера Selenium завершена.")
        return driver

    def get_video_url(self, video_page_url: str) -> Optional[str]:
        try:
            logger.info(f"Открываем страницу: {video_page_url}")
            self.driver.get(video_page_url)

            logger.info("Ищем блок с видео и эмулируем нажатие...")
            h1_element = WebDriverWait(self.driver, 10).until(
                EC.element_to_be_clickable((By.TAG_NAME, "h1"))
            )
            h1_element.click()

            logger.info("Нажатие выполнено.")
            time.sleep(15)

            logger.info("Анализируем запросы браузера...")
            performance_log = self.driver.get_log("performance")
            mp4_urls = []

            for entry in performance_log:
                message = entry.get("message", "")
                if "https://cfvod.kaltura.com/hls/p/" in message:
                    match = re.search(r'"url":"(https://[^"]+\.ts)"', message)
                    if match:
                        ts_url = match.group(1)
                        mp4_url = ts_url.split("/seg-")[0]
                        if mp4_url not in mp4_urls:
                            mp4_urls.append(mp4_url)
                            logger.info(f"Найден MP4 URL: {mp4_url}")

            if mp4_urls:
                return mp4_urls[-1]
        except Exception as e:
            logger.error(f"Ошибка при обработке страницы: {e}")
        return None

    def quit(self) -> None:
        self.driver.quit()
        logger.info("Драйвер Selenium закрыт.")


class VideoDownloader:
    def __init__(self, headless: bool = False, driver_path: Optional[str] = None):
        self.selenium = SeleniumDownloader(headless=headless, driver_path=driver_path)

    def get_video_url(self, video_page_url: str) -> Optional[str]:
        return self.selenium.get_video_url(video_page_url)

    def download_segments(
        self,
        base_url: str,
        video_page_url: str,
        output_dir: Optional[str] = None,
        resume: bool = True,
        progress_callback: Optional[callable] = None,
        stop_event: Optional[object] = None
    ) -> Tuple[bool, Optional[str]]:
        if output_dir is None:
            video_uuid = self._extract_uuid(video_page_url)
            output_dir = os.path.join(".", "video", video_uuid)

        os.makedirs(output_dir, exist_ok=True)
        logger.info(f"Каталог '{output_dir}' готов.")

        start_segment = 1
        if resume:
            start_segment = self._get_last_valid_segment(output_dir) + 1

        downloaded_segments = []
        file_number = start_segment
        max_retries = 3

        while True:
            # Проверка на остановку
            if stop_event and stop_event.is_set():
                logger.info(f"Загрузка остановлена на сегменте {file_number}")
                break

            filename = f"seg-{file_number}-v1-a1.ts"
            ts_url = f"{base_url}/{filename}"
            output_path = os.path.join(output_dir, filename)

            command = [
                "ffmpeg",
                "-hide_banner",
                "-loglevel", "error",
                "-i", ts_url,
                "-c", "copy",
                "-user_agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "-headers", "Accept: */*",
                "-headers", "Accept-Language: ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
                "-headers", "Connection: keep-alive",
                "-reconnect", "1",
                "-reconnect_at_eof", "1",
                "-reconnect_streamed", "1",
                "-reconnect_delay_max", "2",
                output_path
            ]

            logger.info(f"Запуск: seg-{file_number}")
            
            if progress_callback:
                progress_callback("downloading", f"Скачивается сегмент {file_number}...")
            
            # Попытка скачать сегмент с повторами
            success = False
            for attempt in range(max_retries):
                # Проверка на остановку перед каждой попыткой
                if stop_event and stop_event.is_set():
                    logger.info(f"Загрузка остановлена на сегменте {file_number}")
                    break
                    
                try:
                    result = subprocess.run(command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
                    logger.info(f"Скачан: {filename}")
                    
                    # Проверяем целостность файла через ffprobe
                    if self._validate_ts_file(output_path):
                        downloaded_segments.append(filename)
                        if progress_callback:
                            progress_callback("progress", f"Скачан сегмент {file_number}")
                        file_number += 1
                        success = True
                        break
                    else:
                        logger.warning(f"Сегмент {filename} повреждён, удаляем и перекачиваем (попытка {attempt + 1}/{max_retries})")
                        if os.path.exists(output_path):
                            os.remove(output_path)
                except subprocess.CalledProcessError as e:
                    logger.warning(f"Ошибка скачивания сегмента {filename} (попытка {attempt + 1}/{max_retries}): {e.stderr.decode() if e.stderr else str(e)}")
                    if os.path.exists(output_path):
                        try:
                            os.remove(output_path)
                        except:
                            pass
            
            if not success:
                logger.info(f"Не удалось скачать сегмент {filename} после {max_retries} попыток")
                break

        return len(downloaded_segments) > 0, output_dir

    def _validate_ts_file(self, file_path: str) -> bool:
        """Проверяет целостность .ts файла через ffprobe."""
        if not os.path.exists(file_path):
            return False
        
        # Проверяем размер файла
        if os.path.getsize(file_path) < 1000:
            logger.warning(f"Файл {file_path} слишком маленький ({os.path.getsize(file_path)} байт)")
            return False
        
        # Используем ffprobe для проверки
        command = [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            file_path
        ]
        
        try:
            result = subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)
            duration = result.stdout.decode().strip()
            if duration and float(duration) > 0:
                return True
            return False
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, ValueError) as e:
            logger.warning(f"ffprobe не смог проверить файл {file_path}: {e}")
            return False

    def _get_last_valid_segment(self, directory: str) -> int:
        """Возвращает номер последнего валидного сегмента."""
        if not os.path.exists(directory):
            return 0
        
        max_number = 0
        for filename in os.listdir(directory):
            match = re.search(r"seg-(\d+)-", filename)
            if match:
                seg_num = int(match.group(1))
                # Проверяем валидность файла
                file_path = os.path.join(directory, filename)
                if self._validate_ts_file(file_path):
                    max_number = max(max_number, seg_num)
                else:
                    logger.info(f"Найден повреждённый сегмент: {filename}, будет перекачан")
                    try:
                        os.remove(file_path)
                    except:
                        pass
        
        return max_number

    def _extract_uuid(self, video_page_url: str) -> str:
        return Path(video_page_url).name

    def concat_segments(self, video_page_url: str, output_filename: Optional[str] = None) -> Optional[str]:
        video_uuid = self._extract_uuid(video_page_url)
        directory = os.path.join(".", "video", video_uuid)

        ts_files = sorted(
            [f for f in os.listdir(directory) if f.endswith(".ts")],
            key=natural_sort_key
        )

        logger.info(f"Найдено {len(ts_files)} .ts файлов.")

        if not ts_files:
            return None

        if output_filename is None:
            output_filename = os.path.join(directory, "output.ts")

        file_list_path = os.path.join(directory, "file_list.txt")
        with open(file_list_path, "w", encoding="utf-8") as file_list:
            for ts_file in ts_files:
                file_list.write(f"file '{ts_file}'\n")

        command = [
            "ffmpeg",
            "-f", "concat",
            "-safe", "0",
            "-i", file_list_path,
            "-c", "copy",
            output_filename
        ]

        logger.info(f"Конкатенация файлов...")
        try:
            subprocess.run(command, check=True)
            logger.info(f"Файлы успешно объединены в: {output_filename}")
            return output_filename
        except subprocess.CalledProcessError as e:
            logger.error(f"Ошибка при объединении файлов: {e}")
            return None

    def download_full(
        self,
        video_page_url: str,
        concat: bool = True,
        resume: bool = True,
        progress_callback: Optional[callable] = None,
        stop_event: Optional[object] = None
    ) -> Tuple[bool, Optional[str]]:
        mp4_url = self.get_video_url(video_page_url)
        if not mp4_url:
            logger.error("MP4 URL не найден.")
            return False, None

        logger.info(f"Найден MP4 URL: {mp4_url}")

        success, output_dir = self.download_segments(
            mp4_url, video_page_url, 
            resume=resume,
            progress_callback=progress_callback,
            stop_event=stop_event
        )
        if not success:
            return False, None

        if concat:
            output_file = self.concat_segments(video_page_url)
            return output_file is not None, output_file

        return True, output_dir

    def close(self) -> None:
        self.selenium.quit()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
