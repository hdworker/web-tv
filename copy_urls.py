import logging
import requests
from bs4 import BeautifulSoup
import pandas as pd
import sys

# Настройка логгера
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

def save_to_csv(data, filename="video_links"):
    """Сохраняет данные в CSV-файл."""
    try:
        # Создаем DataFrame из данных
        df = pd.DataFrame(data)
        # Сохраняем в CSV
        # datetime_label = pd.Timestamp.now().strftime("%Y-%m-%d")
        filename_date = f"{filename}_{sys.argv[1]}.csv"
        df.to_csv(filename_date, index=False)
        logger.info(f"Данные успешно сохранены в файл {filename_date}")
    except Exception as e:
        logger.error(f"Ошибка при сохранении данных в CSV: {e}")

def get_video_links(url):
    """Извлекает ссылки на страницы видеотрансляций."""
    try:
        # Загружаем страницу
        response = requests.get(url)
        response.raise_for_status()  # Проверка на ошибки
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Ищем все ссылки внутри блоков с указанной структурой
        video_links = []
        for a in soup.find_all('a', href=True):
            # Проверяем, есть ли внутри блока заголовок и ссылка
            title_div = a.find('div', class_='field__item')
            if title_div and 'media-asset__title' in str(a):
                full_url = "https://webtv.un.org" + a['href']  # Получаем полный URL
                video_links.append(full_url)
        
        return video_links
    except requests.exceptions.RequestException as e:
        logger.error(f"Ошибка при загрузке страницы: {e}")
        return []

def main():
    if len(sys.argv) != 2:
            print("Usage: python copy_urls.py date_like_2025-04-02")
            sys.exit(1)
    
    date_shed = sys.argv[1]
    url = f"https://webtv.un.org/en/schedule/{date_shed}"
 
    logger.info(f"Начинаем парсинг страницы: {url}")
    
    # Получаем ссылки на видео
    links = get_video_links(url)
    
    if links:
        logger.info(f"Найдено ссылок на видеотрансляции: {len(links)}")
        for i, link in enumerate(links, start=1):
            logger.info(f"{i}. {link}")
    else:
        logger.warning("Ссылки на видеотрансляции не найдены.")

    save_to_csv(links)

if __name__ == "__main__":
    main()
