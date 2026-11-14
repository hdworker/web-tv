import logging
import os
import time
import json
from pathlib import Path
from typing import Optional, Tuple
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

logger = logging.getLogger(__name__)


class RutubeUploader:
    def __init__(self, cookies_path: str = "rutube_cookies.json", headless: bool = False):
        self.cookies_path = cookies_path
        self.headless = headless
        self.driver = None
        self._init_driver()
        
        logger.info(f"RutubeUploader инициализирован (headless={headless})")
        
        if os.path.exists(self.cookies_path):
            logger.info("Файл cookies найден, пробуем загрузить...")
            if self.load_cookies():
                logger.info("Cookies загружены успешно")
            else:
                logger.warning("Не удалось загрузить cookies")
        else:
            logger.info("Файл cookies не найден, нужно войти вручную")

    def _init_driver(self) -> None:
        chrome_options = Options()
        if self.headless:
            chrome_options.add_argument("--headless=new")
            chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--log-level=3")
        chrome_options.add_argument("--mute-audio")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        
        try:
            import chromedriver_autoinstaller
            chromedriver_autoinstaller.install()
        except ImportError:
            pass
        
        self.driver = webdriver.Chrome(options=chrome_options)
        self.wait = WebDriverWait(self.driver, 30)
        logger.info("Драйвер Selenium инициализирован")

    def save_cookies(self) -> None:
        if self.driver:
            cookies = self.driver.get_cookies()
            with open(self.cookies_path, "w") as f:
                json.dump(cookies, f)
            logger.info(f"Cookies сохранены в {self.cookies_path}")
            logger.info(f"Сохранено {len(cookies)} cookies")

    def load_cookies(self) -> bool:
        logger.info(f"Загрузка cookies из {self.cookies_path}")
        if not os.path.exists(self.cookies_path):
            logger.warning("Файл cookies не существует")
            return False
        
        self.driver.get("https://rutube.ru")
        time.sleep(3)
        logger.info("Страница rutube.ru загружена")
        
        try:
            with open(self.cookies_path, "r") as f:
                cookies = json.load(f)
            logger.info(f"Найдено {len(cookies)} cookies для загрузки")
            
            for i, cookie in enumerate(cookies):
                if 'sameSite' in cookie:
                    del cookie['sameSite']
                self.driver.add_cookie(cookie)
                logger.debug(f"Добавлен cookie {i+1}: {cookie.get('name', 'unknown')}")
            
            logger.info("Все cookies добавлены, обновляем страницу...")
            self.driver.refresh()
            time.sleep(3)
            
            if self._is_logged_in():
                logger.info("✓ Пользователь авторизован")
                return True
            else:
                logger.warning("✗ Пользователь не авторизован после загрузки cookies")
        except Exception as e:
            logger.error(f"Ошибка при загрузке cookies: {e}")
        
        return False

    def _is_logged_in(self) -> bool:
        try:
            self.driver.find_element(By.CSS_SELECTOR, "img[alt='py_webuntv']")
            return True
        except NoSuchElementException:
            pass
        
        try:
            self.driver.find_element(By.CSS_SELECTOR, "img[class*='_image_']")
            return True
        except NoSuchElementException:
            pass
        
        try:
            self.driver.find_element(By.XPATH, "//a[contains(@href, '/profile/')]")
            return True
        except NoSuchElementException:
            pass
        
        return False

    def login(self, username: str, password: str) -> bool:
        self.driver.get("https://rutube.ru/auth/")
        time.sleep(3)
        
        try:
            username_input = self.wait.until(
                EC.presence_of_element_located((By.NAME, "username"))
            )
            password_input = self.driver.find_element(By.NAME, "password")
            
            username_input.clear()
            username_input.send_keys(username)
            password_input.clear()
            password_input.send_keys(password)
            
            login_button = self.driver.find_element(
                By.CSS_SELECTOR, 
                "button[type='submit']"
            )
            login_button.click()
            
            time.sleep(5)
            
            if self._is_logged_in():
                self.save_cookies()
                logger.info("Успешный вход в аккаунт")
                return True
            
            logger.warning("Не удалось войти. Возможно, требуется капча.")
            return False
            
        except Exception as e:
            logger.error(f"Ошибка при входе: {e}")
            return False

    def upload_video(
        self, 
        file_path: str, 
        title: str, 
        description: str,
        tags: Optional[str] = None,
        category: Optional[str] = None
    ) -> Tuple[bool, Optional[str]]:
        logger.info("=" * 50)
        logger.info("НАЧАЛО ЗАГРУЗКИ ВИДЕО")
        logger.info(f"Файл: {file_path}")
        logger.info(f"Название: {title[:50]}..." if len(title) > 50 else f"Название: {title}")
        logger.info(f"Описание: {description[:50]}..." if len(description) > 50 else f"Описание: {description}")
        if tags:
            logger.info(f"Теги: {tags}")
        logger.info("=" * 50)
        
        if not os.path.exists(file_path):
            logger.error(f"Файл не найден: {file_path}")
            return False, None
        
        logger.info("Открытие studio.rutube.ru...")
        self.driver.get("https://studio.rutube.ru")
        time.sleep(3)
        logger.info(f"Текущий URL: {self.driver.current_url}")
        
        try:
            self._click_add_button()
            
            self._click_upload_video_option()
            
            self._select_file(file_path)
            
            self._fill_video_info(title, description, tags)
            
            return self._wait_for_upload_complete()
            
        except Exception as e:
            logger.error(f"Ошибка при загрузке видео: {e}")
            self._take_screenshot("error.png")
            return False, None

    def _click_add_button(self) -> None:
        logger.info("Нажатие кнопки 'Добавить'...")
        
        add_button = self.wait.until(
            EC.element_to_be_clickable((By.XPATH, "//span[text()='Добавить']"))
        )
        add_button.click()
        time.sleep(2)
        logger.info("Кнопка 'Добавить' нажата")

    def _click_upload_video_option(self) -> None:
        logger.info("Выбор 'Загрузить видео или Shorts'...")
        
        upload_option = self.wait.until(
            EC.element_to_be_clickable(
                (By.XPATH, "//div[text()='Загрузить видео или Shorts']")
            )
        )
        upload_option.click()
        time.sleep(3)
        logger.info("Выбрано 'Загрузить видео'")

    def _select_file(self, file_path: str) -> None:
        logger.info("Нажатие кнопки 'Выбрать файлы'...")
        
        select_files_button = self.wait.until(
            EC.element_to_be_clickable(
                (By.XPATH, "//span[text()='Выбрать файлы']")
            )
        )
        select_files_button.click()
        time.sleep(2)
        
        file_input = self.wait.until(
            EC.presence_of_element_located(
                (By.CSS_SELECTOR, "input[type='file']")
            )
        )
        
        absolute_path = os.path.abspath(file_path)
        file_input.send_keys(absolute_path)
        logger.info(f"Файл выбран: {file_path}")

    def _fill_video_info(
        self, 
        title: str, 
        description: str,
        tags: Optional[str] = None
    ) -> None:
        logger.info("Заполнение информации о видео...")
        
        time.sleep(5)
        
        title_inputs = self.driver.find_elements(By.CSS_SELECTOR, "input")
        for inp in title_inputs:
            placeholder = inp.get_attribute("placeholder") or ""
            if "названи" in placeholder.lower() or "title" in placeholder.lower():
                inp.clear()
                inp.send_keys(title)
                logger.info(f"Название добавлено: {title[:30]}...")
                break
        
        time.sleep(1)
        
        textareas = self.driver.find_elements(By.CSS_SELECTOR, "textarea")
        for textarea in textareas:
            placeholder = textarea.get_attribute("placeholder") or ""
            if "описани" in placeholder.lower() or "description" in placeholder.lower():
                textarea.clear()
                textarea.send_keys(description)
                logger.info("Описание добавлено")
                break

    def _wait_for_upload_complete(self) -> Tuple[bool, Optional[str]]:
        logger.info("Ожидание завершения загрузки...")
        
        max_wait = 900
        check_interval = 15
        elapsed = 0
        last_url = ""
        
        while elapsed < max_wait:
            time.sleep(check_interval)
            elapsed += check_interval
            
            current_url = self.driver.current_url
            
            if current_url != last_url:
                logger.info(f"Текущий URL: {current_url}")
                last_url = current_url
            
            if "/video/" in current_url and "studio" not in current_url:
                video_id = self._extract_video_id(current_url)
                if video_id:
                    video_url = f"https://rutube.ru/video/{video_id}/"
                    logger.info(f"Видео загружено: {video_url}")
                    return True, video_url
            
            try:
                progress_elements = self.driver.find_elements(
                    By.CSS_SELECTOR, 
                    "[class*='progress'], [class*='upload']"
                )
                for el in progress_elements:
                    if el.is_displayed():
                        text = el.text
                        if text:
                            logger.info(f"Прогресс: {text}")
            except:
                pass
            
            try:
                error_elements = self.driver.find_elements(
                    By.CSS_SELECTOR, 
                    "[class*='error'], [class*='Error']"
                )
                for el in error_elements:
                    if el.is_displayed() and el.text:
                        logger.error(f"Ошибка: {el.text}")
                        return False, None
            except:
                pass
        
        logger.error("Превышен таймаут ожидания загрузки")
        return False, None

    def _extract_video_id(self, url: str) -> Optional[str]:
        import re
        patterns = [
            r"rutube\.ru/video/([a-f0-9]+)/?",
            r"rutube\.ru/video/[\w-]+/([a-f0-9]+)/?"
        ]
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None

    def _take_screenshot(self, filename: str) -> None:
        try:
            self.driver.save_screenshot(filename)
            logger.info(f"Скриншот сохранен: {filename}")
        except Exception as e:
            logger.warning(f"Не удалось сделать скриншот: {e}")

    def close(self) -> None:
        if self.driver:
            self.driver.quit()
            logger.info("Драйвер закрыт")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
