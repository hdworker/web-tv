import argparse
import logging
import sys
import os
from pathlib import Path
from typing import Optional

from database import Database, Video
from parser import VideoPageParser

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)


def add_video_to_db(
    video_url: str,
    local_path: str,
    db_path: str = "un_videos.db"
) -> Optional[int]:
    db = Database(db_path)
    
    parser = VideoPageParser()
    parser.enable_logging(False)
    metadata = parser.parse(video_url)
    
    if not metadata.title:
        logger.error("Не удалось получить метаданные видео")
        return -1
    
    video = Video(
        un_video_url=video_url,
        local_video_path=local_path,
        title=metadata.title,
        description=metadata.description,
        duration=metadata.video_length,
        languages=metadata.original_languages,
        date=metadata.production_date,
        status="ready"
    )
    
    video_id = db.add_video(video)
    logger.info(f"Видео добавлено в БД с ID: {video_id}")
    return video_id


def add_videos_from_directory(
    directory: str,
    db_path: str = "un_videos.db",
    video_url: Optional[str] = None
) -> int:
    video_path = Path(directory)
    if not video_path.exists():
        logger.error(f"Каталог не найден: {directory}")
        return -1
    
    video_files = list(video_path.glob("*.mp4")) + list(video_path.glob("*.ts"))
    
    if not video_files:
        logger.warning(f"Видео файлы в каталоге не найдены: {directory}")
        return 0
    
    count = 0
    for video_file in video_files:
        logger.info(f"Добавление: {video_file.name}")
        
        if video_url:
            video_id = add_video_to_db(video_url, str(video_file), db_path)
            if video_id is not None and video_id > 0:
                count += 1
        else:
            db = Database(db_path)
            video = Video(
                local_video_path=str(video_file),
                title=video_file.stem,
                status="ready"
            )
            db.add_video(video)
            count += 1
    
    logger.info(f"Добавлено {count} видео")
    return count


def main():
    parser = argparse.ArgumentParser(description="Добавить видео в базу данных")
    subparsers = parser.add_subparsers(dest="command", help="Команды")
    
    url_parser = subparsers.add_parser("url", help="Добавить видео по URL")
    url_parser.add_argument("video_url", help="URL видео на UN")
    url_parser.add_argument("local_path", help="Локальный путь к видео файлу")
    url_parser.add_argument("--db", default="un_videos.db", help="Путь к базе данных")
    
    dir_parser = subparsers.add_parser("dir", help="Добавить видео из каталога")
    dir_parser.add_argument("directory", help="Каталог с видео файлами")
    dir_parser.add_argument("--db", default="un_videos.db", help="Путь к базе данных")
    dir_parser.add_argument("--url", help="URL видео (один для всех файлов)")
    
    list_parser = subparsers.add_parser("list", help="Список видео в базе")
    list_parser.add_argument("--db", default="un_videos.db", help="Путь к базе данных")
    list_parser.add_argument("--status", help="Фильтр по статусу")
    list_parser.add_argument("--limit", type=int, default=50, help="Лимит записей")
    
    args = parser.parse_args()
    
    if args.command == "url":
        video_id = add_video_to_db(args.video_url, args.local_path, args.db)
        sys.exit(0 if video_id is not None and video_id > 0 else 1)
    
    elif args.command == "dir":
        count = add_videos_from_directory(args.directory, args.db, args.url)
        sys.exit(0 if count >= 0 else 1)
    
    elif args.command == "list":
        db = Database(args.db)
        videos = db.get_videos(status=args.status, limit=args.limit)
        
        if not videos:
            print("Видео не найдены")
            sys.exit(0)
        
        print(f"\n{'ID':<5} {'Статус':<12} {'Название':<40}")
        print("-" * 60)
        for v in videos:
            title = v.title[:37] + "..." if len(v.title) > 40 else v.title
            print(f"{v.id:<5} {v.status:<12} {title:<40}")
        print(f"\nВсего: {len(videos)}")
    
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
