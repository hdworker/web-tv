import argparse
import logging
import sys
from pathlib import Path

from rutube import RutubeUploader
from database import Database, Video

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)


def upload_from_db(video_id: int, db_path: str = "un_videos.db", headless: bool = False) -> bool:
    db = Database(db_path)
    video = db.get_video(video_id)
    
    if not video:
        logger.error(f"Видео с ID {video_id} не найдено")
        return False
    
    if not video.local_video_path:
        logger.error(f"Локальный путь к видео не указан")
        return False
    
    video_path = Path(video.local_video_path)
    if not video_path.exists():
        logger.error(f"Файл не найден: {video_path}")
        return False
    
    logger.info(f"Загрузка видео: {video.title}")
    logger.info(f"Путь к файлу: {video_path}")
    logger.info(f"Описание: {video.description[:100]}...")
    
    db.update_video(video_id, status="uploading")
    
    try:
        with RutubeUploader(headless=headless) as uploader:
            if not uploader.load_cookies():
                logger.warning("Cookies не загружены. Требуется вход.")
                logger.info("Пожалуйста, войдите в аккаунт в открывшемся браузере")
                return False
            
            success, video_url = uploader.upload_video(
                file_path=str(video_path),
                title=video.title,
                description=video.description
            )
            
            if success and video_url:
                db.update_video(
                    video_id,
                    rutube_video_url=video_url,
                    status="uploaded"
                )
                logger.info(f"Видео успешно загружено: {video_url}")
                return True
            else:
                db.update_video(video_id, status="upload_failed")
                logger.error("Загрузка не удалась")
                return False
                
    except Exception as e:
        logger.error(f"Ошибка при загрузке: {e}")
        db.update_video(video_id, status="upload_failed")
        return False


def upload_from_file(
    file_path: str,
    title: str,
    description: str,
    tags: str = None,
    headless: bool = False
) -> bool:
    video_path = Path(file_path)
    if not video_path.exists():
        logger.error(f"Файл не найден: {file_path}")
        return False
    
    try:
        with RutubeUploader(headless=headless) as uploader:
            if not uploader.load_cookies():
                logger.warning("Cookies не загружены. Требуется вход.")
                return False
            
            success, video_url = uploader.upload_video(
                file_path=str(video_path),
                title=title,
                description=description,
                tags=tags
            )
            
            if success and video_url:
                logger.info(f"Видео успешно загружено: {video_url}")
                return True
            else:
                logger.error("Загрузка не удалась")
                return False
                
    except Exception as e:
        logger.error(f"Ошибка при загрузке: {e}")
        return False


def login(username: str, password: str, headless: bool = False) -> bool:
    try:
        with RutubeUploader(headless=headless) as uploader:
            success = uploader.login(username, password)
            if success:
                logger.info("Вход выполнен, cookies сохранены")
            return success
    except Exception as e:
        logger.error(f"Ошибка при входе: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Загрузка видео на Rutube")
    subparsers = parser.add_subparsers(dest="command", help="Команды")
    
    login_parser = subparsers.add_parser("login", help="Вход в аккаунт Rutube")
    login_parser.add_argument("username", help="Имя пользователя")
    login_parser.add_argument("password", help="Пароль")
    login_parser.add_argument("--headless", action="store_true", help="Запуск в headless режиме")
    
    upload_parser = subparsers.add_parser("upload", help="Загрузить видео")
    upload_parser.add_argument("file", help="Путь к видео файлу")
    upload_parser.add_argument("--title", required=True, help="Название видео")
    upload_parser.add_argument("--description", required=True, help="Описание видео")
    upload_parser.add_argument("--tags", help="Теги через запятую")
    upload_parser.add_argument("--headless", action="store_true", help="Запуск в headless режиме")
    
    upload_db_parser = subparsers.add_parser("upload-db", help="Загрузить видео из БД")
    upload_db_parser.add_argument("video_id", type=int, help="ID видео в базе данных")
    upload_db_parser.add_argument("--db", default="un_videos.db", help="Путь к базе данных")
    upload_db_parser.add_argument("--headless", action="store_true", help="Запуск в headless режиме (по умолчанию: видимый браузер)")
    
    args = parser.parse_args()
    
    logger.info(f"Режим headless: {args.headless}")
    
    if args.command == "login":
        if not args.headless:
            logger.info("Откроется браузер для входа в аккаунт")
        success = login(args.username, args.password, args.headless)
        sys.exit(0 if success else 1)
    
    elif args.command == "upload":
        success = upload_from_file(
            args.file,
            args.title,
            args.description,
            args.tags,
            args.headless
        )
        sys.exit(0 if success else 1)
    
    elif args.command == "upload-db":
        success = upload_from_db(args.video_id, args.db, args.headless)
        sys.exit(0 if success else 1)
    
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
