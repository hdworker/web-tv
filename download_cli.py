import sys
import argparse
import logging

from downloader import VideoDownloader

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Скачивание видео с UN WebTV")
    parser.add_argument("url", nargs="?", help="URL видео на сайте ООН")
    parser.add_argument(
        "--date", "-d",
        help="Дата для загрузки списка ссылок из файла video_links_YYYY-MM-DD.csv"
    )
    parser.add_argument(
        "--headless", action="store_true",
        help="Запуск браузера в фоновом режиме"
    )
    parser.add_argument(
        "--no-concat", action="store_true",
        help="Не склеивать .ts сегменты в один файл"
    )
    parser.add_argument(
        "--no-resume", action="store_true",
        help="Начать загрузку сначала, не продолжать"
    )

    args = parser.parse_args()

    if args.date:
        import os
        filename = f"video_links_{args.date}.csv"
        if not os.path.exists(filename):
            logger.error(f"Файл не найден: {filename}")
            sys.exit(1)

        with open(filename, "r", encoding="utf-8") as f:
            links = [line.strip() for line in f if line.strip()]

        if not links:
            logger.error(f"В файле {filename} нет ссылок")
            sys.exit(1)

        logger.info(f"Загружаем {len(links)} видео из {filename}")
        success_count = 0

        with VideoDownloader(headless=args.headless) as downloader:
            for i, link in enumerate(links, 1):
                logger.info(f"[{i}/{len(links)}] Обрабатываем: {link}")
                success, _ = downloader.download_full(
                    link,
                    concat=not args.no_concat,
                    resume=not args.no_resume
                )
                if success:
                    success_count += 1

        logger.info(f"Готово. Успешно: {success_count}/{len(links)}")

    elif args.url:
        with VideoDownloader(headless=args.headless) as downloader:
            success, output = downloader.download_full(
                args.url,
                concat=not args.no_concat,
                resume=not args.no_resume
            )
            if success:
                logger.info(f"Видео сохранено: {output}")
            else:
                logger.error("Не удалось скачать видео")
                sys.exit(1)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
