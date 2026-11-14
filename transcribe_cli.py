import argparse
import logging
import sys
import os
from pathlib import Path

from transcriber import VideoTranscriber
from summarizer import TextSummarizer
from database import Database, Transcription

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)


def transcribe_video(
    video_path: str,
    language: str = None,
    output_file: str = None,
    db_path: str = "un_videos.db",
    video_id: int = None
) -> bool:
    if not os.path.exists(video_path):
        logger.error(f"Видео файл не найден: {video_path}")
        return False

    transcriber = VideoTranscriber()
    
    logger.info(f"Начало транскрипции: {video_path}")
    success, result = transcriber.transcribe(video_path, language=language)
    
    if not success or result is None:
        logger.error("Транскрипция не удалась")
        return False

    transcript_text = result["text"]
    logger.info(f"Текст распознан, длина: {len(transcript_text)} символов")

    if output_file:
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(transcript_text)
        logger.info(f"Транскрипция сохранена: {output_path}")

    if video_id:
        db = Database(db_path)
        transcription = Transcription(
            video_id=video_id,
            language=result.get("language", "unknown"),
            transcript_text=transcript_text
        )
        db.add_transcription(transcription)
        db.update_video(video_id, status="transcribed")
        logger.info(f"Транскрипция сохранена в БД для видео ID: {video_id}")

    return True


def summarize_transcript(
    transcript_path: str = None,
    text: str = None,
    output_file: str = None,
    db_path: str = "un_videos.db",
    video_id: int = None,
    translate_to: str = None
) -> bool:
    if transcript_path and os.path.exists(transcript_path):
        with open(transcript_path, "r", encoding="utf-8") as f:
            text = f.read()
    
    if not text:
        logger.error("Текст не предоставлен")
        return False

    summarizer = TextSummarizer()

    if translate_to:
        logger.info(f"Перевод текста на {translate_to}...")
        success, result = summarizer.translate(text, translate_to)
        if not success:
            logger.error("Перевод не удался")
            return False
        text = result
        logger.info(f"Перевод выполнен, длина: {len(text)} символов")

    logger.info("Создание суммаризации...")
    success, summary = summarizer.summarize(text)
    
    if not success or summary is None:
        logger.error("Суммаризация не удалась")
        return False

    logger.info(f"Суммаризация создана, длина: {len(summary)} символов")

    if output_file:
        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(summary)
        logger.info(f"Суммаризация сохранена: {output_path}")

    if video_id:
        db = Database(db_path)
        
        existing = db.get_transcriptions(video_id)
        if existing:
            for t in existing:
                if t.transcript_text == text or translate_to:
                    db.update_transcription(t.id, summary_text=summary)
                    logger.info(f"Суммаризация обновлена для транскрипции ID: {t.id}")
        else:
            transcription = Transcription(
                video_id=video_id,
                language=translate_to or "ru",
                transcript_text=text,
                summary_text=summary
            )
            db.add_transcription(transcription)
            logger.info(f"Суммаризация сохранена в БД для видео ID: {video_id}")

    print("\n" + "=" * 50)
    print("СУММАРИЗАЦИЯ:")
    print("=" * 50)
    print(summary)
    print("=" * 50)

    return True


def full_pipeline(
    video_path: str,
    video_id: int = None,
    language: str = None,
    translate_to: str = None,
    db_path: str = "un_videos.db",
    output_dir: str = None
) -> bool:
    if not os.path.exists(video_path):
        logger.error(f"Видео файл не найден: {video_path}")
        return False

    if output_dir:
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        transcript_file = str(output_path / "transcript.txt")
        summary_file = str(output_path / "summary.txt")
    else:
        video_name = Path(video_path).stem
        transcript_file = f"{video_name}_transcript.txt"
        summary_file = f"{video_name}_summary.txt"

    success = transcribe_video(
        video_path=video_path,
        language=language,
        output_file=transcript_file,
        db_path=db_path,
        video_id=video_id
    )

    if not success:
        return False

    success = summarize_transcript(
        transcript_path=transcript_file if os.path.exists(transcript_file) else None,
        output_file=summary_file,
        db_path=db_path,
        video_id=video_id,
        translate_to=translate_to
    )

    return success


def main():
    parser = argparse.ArgumentParser(description="Транскрипция и суммаризация видео")
    subparsers = parser.add_subparsers(dest="command", help="Команды")

    transcribe_parser = subparsers.add_parser("transcribe", help="Транскрибировать видео")
    transcribe_parser.add_argument("video", help="Путь к видео файлу")
    transcribe_parser.add_argument("--lang", help="Язык видео (en, ru, etc)")
    transcribe_parser.add_argument("--output", help="Путь для сохранения текста")
    transcribe_parser.add_argument("--db", default="un_videos.db", help="Путь к базе данных")
    transcribe_parser.add_argument("--video-id", type=int, help="ID видео в базе")

    summarize_parser = subparsers.add_parser("summarize", help="Создать суммаризацию")
    summarize_parser.add_argument("text", help="Текст для суммаризации или путь к файлу")
    summarize_parser.add_argument("--output", help="Путь для сохранения")
    summarize_parser.add_argument("--db", default="un_videos.db", help="Путь к базе данных")
    summarize_parser.add_argument("--video-id", type=int, help="ID видео в базе")
    summarize_parser.add_argument("--translate", help="Перевести на язык (ru, en, etc)")

    pipeline_parser = subparsers.add_parser("pipeline", help="Полный цикл: транскрипция + суммаризация")
    pipeline_parser.add_argument("video", help="Путь к видео файлу")
    pipeline_parser.add_argument("--lang", help="Язык видео")
    pipeline_parser.add_argument("--translate", help="Перевести транскрипцию на язык")
    pipeline_parser.add_argument("--db", default="un_videos.db", help="Путь к базе данных")
    pipeline_parser.add_argument("--video-id", type=int, help="ID видео в базе")
    pipeline_parser.add_argument("--output-dir", help="Каталог для сохранения результатов")

    args = parser.parse_args()

    if args.command == "transcribe":
        success = transcribe_video(
            args.video,
            args.lang,
            args.output,
            args.db,
            args.video_id
        )
        sys.exit(0 if success else 1)

    elif args.command == "summarize":
        text = args.text
        if os.path.isfile(args.text):
            with open(args.text, "r", encoding="utf-8") as f:
                text = f.read()
        
        success = summarize_transcript(
            text=text,
            output_file=args.output,
            db_path=args.db,
            video_id=args.video_id,
            translate_to=args.translate
        )
        sys.exit(0 if success else 1)

    elif args.command == "pipeline":
        success = full_pipeline(
            args.video,
            args.video_id,
            args.lang,
            args.translate,
            args.db,
            args.output_dir
        )
        sys.exit(0 if success else 1)

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
