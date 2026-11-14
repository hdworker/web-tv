import logging
from typing import Optional

logger = logging.getLogger(__name__)


def fetch_html_with_selenium(url: str, headless: bool = True) -> Optional[str]:
    """
    Загружает страницу через Selenium (Chrome) и возвращает HTML после полной загрузки.
    """
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.common.by import By
        import chromedriver_autoinstaller
    except ImportError as e:
        logger.error(f"Не удалось импортировать Selenium: {e}. Установите selenium и chromedriver-autoinstaller.")
        return None

    logger.info("Инициализация Selenium Chrome драйвера...")
    chromedriver_autoinstaller.install()
    chrome_options = Options()
    if headless:
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--log-level=3")
    chrome_options.add_argument("--mute-audio")
    # New options
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)

    driver = webdriver.Chrome(options=chrome_options)
    # New options
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

    try:
        logger.info(f"Открываем страницу: {url}")
        driver.get(url)
        # Ждём загрузки страницы (ожидаем наличие элемента body)
        WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )
        # Дополнительное ожидание для AJAX-контента (транскрипт может подгружаться позже)
        import time
        time.sleep(5)
        html = driver.page_source
        logger.info(f"HTML загружен через Selenium, размер: {len(html)} символов")
        return html
    except Exception as e:
        logger.error(f"Ошибка при загрузке страницы через Selenium: {e}")
        return None
    finally:
        driver.quit()
        logger.info("Драйвер Selenium закрыт.")


def extract_transcript_from_html(html: str) -> str:
    """
    Извлекает транскрипт из HTML с помощью BeautifulSoup.
    """
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, 'html.parser')

    # Поиск корневого элемента транскрипта
    root = soup.find('div', class_=lambda x: x and 'transcript__root' in x)
    if not root:
        logger.warning("Корневой элемент транскрипта не найден. Возможно, транскрипт отсутствует.")
        return ""

    # Поиск всех caption
    captions = root.find_all('div', class_=lambda x: x and 'caption__caption' in x)
    logger.info(f"Найдено элементов caption: {len(captions)}")

    result = []
    for cap in captions:
        time_elem = cap.find('div', class_=lambda x: x and 'caption__caption-time' in x)
        text_elem = cap.find('span')
        timestamp = time_elem.text.strip() if time_elem else ""
        text = text_elem.text.strip() if text_elem else ""
        if text:
            result.append(f"[{timestamp}] {text}")

    full_transcript = "\n".join(result)
    logger.info(f"Сформирован транскрипт из {len(result)} фрагментов.")
    return full_transcript


def extract_transcript_from_url(url: str, use_selenium: bool = True) -> str:
    """
    Извлекает транскрипт со страницы UN WebTV.
    """
    html = None
    if use_selenium:
        html = fetch_html_with_selenium(url, headless=False)
    else:
        # Используем requests через parser
        from parser import VideoPageParser
        parser = VideoPageParser()
        html = parser._fetch_html(url)

    if not html:
        logger.error("Не удалось загрузить HTML.")
        return ""

    return extract_transcript_from_html(html)