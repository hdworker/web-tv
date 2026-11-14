import logging
import threading
from typing import Optional, Tuple, Dict, Any
from downloader import VideoDownloader

logger = logging.getLogger(__name__)


class VideoDownloadService:
    """
    Сервис для управления загрузкой видео.
    Инкапсулирует логику работы с VideoDownloader и управление состоянием загрузок.
    """

    def __init__(self):
        self.download_state: Dict[int, Dict[str, Any]] = {}
        """Состояние загрузок: video_id -> {"stop_event": threading.Event, "running": bool}"""

    def start_download(
        self,
        video_id: int,
        video_url: str,
        progress_callback: Optional[callable] = None,
        concat: bool = True,
        resume: bool = True
    ) -> Tuple[bool, Optional[str]]:
        """
        Запускает загрузку видео в отдельном потоке.

        :param video_id: ID видео в БД
        :param video_url: URL страницы видео на UN WebTV
        :param progress_callback: Функция для обратного вызова с прогрессом
        :param concat: Нужно ли склеивать сегменты после загрузки
        :param resume: Продолжить с последнего скачанного сегмента
        :return: (успех, путь к выходному файлу или директории)
        """
        stop_event = threading.Event()
        self.download_state[video_id] = {"stop_event": stop_event, "running": True}

        try:
            with VideoDownloader(headless=True) as downloader:
                success, output = downloader.download_full(
                    video_url,
                    concat=concat,
                    resume=resume,
                    progress_callback=progress_callback,
                    stop_event=stop_event
                )
                if stop_event.is_set():
                    logger.info(f"Загрузка видео {video_id} остановлена пользователем.")
                    return False, None
                return success, output
        except Exception as e:
            logger.error(f"Ошибка при загрузке видео {video_id}: {e}")
            return False, None
        finally:
            if video_id in self.download_state:
                self.download_state[video_id]["running"] = False

    def stop_download(self, video_id: int) -> bool:
        """
        Останавливает загрузку видео.

        :param video_id: ID видео
        :return: True если загрузка была остановлена, False если загрузка не найдена
        """
        if video_id in self.download_state:
            self.download_state[video_id]["stop_event"].set()
            return True
        return False

    def concat_segments(self, video_url: str) -> Optional[str]:
        """
        Склеивает сегменты видео.

        :param video_url: URL страницы видео
        :return: Путь к склеенному файлу или None при ошибке
        """
        try:
            with VideoDownloader(headless=True) as downloader:
                return downloader.concat_segments(video_url)
        except Exception as e:
            logger.error(f"Ошибка при склейке сегментов: {e}")
            return None

    def get_segments_info(self, video_url: str) -> Dict[str, Any]:
        """
        Возвращает информацию о скачанных сегментах.

        :param video_url: URL страницы видео
        :return: Словарь с информацией о сегментах
        """
        from downloader import VideoDownloader
        import os
        import re

        video_uuid = video_url.split("/")[-1]
        directory = os.path.join(".", "video", video_uuid)

        if not os.path.exists(directory):
            return {"last_segment": 0, "total_files": 0, "directory": directory}

        downloader = VideoDownloader()
        last_segment = downloader._get_last_valid_segment(directory)
        downloader.close()

        ts_files = [f for f in os.listdir(directory) if f.endswith(".ts")]
        output_file = os.path.exists(os.path.join(directory, "output.ts"))

        return {
            "last_segment": last_segment,
            "total_files": len(ts_files),
            "has_output": output_file,
            "directory": directory
        }

    def is_download_running(self, video_id: int) -> bool:
        """
        Проверяет, выполняется ли загрузка видео.

        :param video_id: ID видео
        :return: True если загрузка выполняется
        """
        if video_id in self.download_state:
            return self.download_state[video_id]["running"]
        return False