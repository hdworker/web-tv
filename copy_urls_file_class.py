import logging
import sys
import pandas as pd
from parser import VideoPageParser

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

def get_video_links(url):
    """
    Извлекает ссылки на страницы видеотрансляций и возвращает список данных.
    
    :param url: URL страницы для парсинга
    :return: Список данных с заголовком, описанием и ссылкой
    """
    parser = VideoPageParser()
    parser.enable_logging(False)
    
    metadata = parser.parse(url)
    
    if metadata.title:
        video_data = [{
            "title": metadata.title,
            "description": metadata.description,
            "link": url,
            "broadcasting_entity": metadata.broadcasting_entity,
            "original_languages": metadata.original_languages,
            "production_date": metadata.production_date,
            "video_length": metadata.video_length,
            "breadcrumbs": metadata.categories,
            "url": url
        }]
        return video_data
    
    return []
    
def save_to_csv(data, filename="video_links.csv"):
    """Сохраняет данные в CSV-файл."""
    try:
        # Создаем DataFrame из данных
        df = pd.DataFrame(data)
        # Сохраняем в CSV
        df.to_csv(filename, index=False)
        logger.info(f"Данные успешно сохранены в файл {filename}")
    except Exception as e:
        logger.error(f"Ошибка при сохранении данных в CSV: {e}")

def save_to_excel(data, filename="video_data"):
    """Сохраняет данные в Excel-файл."""
    try:
        # Создаем DataFrame из данных
        df = pd.DataFrame(data)
        # Сохраняем в Excel
        # datetime_label = datetime.now().strftime("%Y-%m-%d")
        complete_filename = f"{filename}_{sys.argv[1]}.xlsx"
        
        logger.info(f"Данные успешно сохранены в файл {complete_filename}")

        df.to_excel(complete_filename, index=False)

    except Exception as e:
        logger.error(f"Ошибка при сохранении данных в Excel: {e}")

def main():
    if len(sys.argv) != 2:
        print("Usage: python copy_urls_file.py date_like_2025-04-02")
        sys.exit(1)
    
    # url = "https://webtv.un.org/en/schedule"
    date_shed = sys.argv[1]
    # url = f"https://webtv.un.org/en/schedule/{date_shed}"
    # logger.info(f"Начинаем парсинг страницы: {url}")
    
    # Получаем ссылки на видео из файла video_links.csv
    # links = get_video_links(url)
    with open(f"video_links_{date_shed}.csv", "r") as f:
        links = f.readlines()
    
    if links:
        video_data = []
        logger.info(f"Найдено ссылок на видеотрансляции: {len(links)}")
        for i, link in enumerate(links, start=1):
            cleaned_link = link.strip()
            logger.info(f"{i}. {cleaned_link}")
            vd = get_video_links(cleaned_link)
            logger.info(f"Данные видеотрансляции: {vd}")
            video_data.extend(vd)
        save_to_excel(video_data, "video_data")
        logger.info('Файл {video_data} успешно записан.')
    else:
        logger.warning("Ссылки на видеотрансляции не найдены.")

if __name__ == "__main__":
    main()
