"""
Скрипт для "умного" перевода больших текстов с использованием библиотеки translators.

Разбивает текст на чанки с overlap и корректно склеивает переводы.
"""

import argparse
import logging
import os
import sys
import time
from pathlib import Path

import translators as ts

# ============================================================
# НАСТРОЙКИ МОДУЛЯ
# ============================================================

CHUNK_SIZE = 10000
OVERLAP_SIZE = 500
MAX_RETRIES = 3
RETRY_DELAY = 2

TRANSLATORS_PRIORITY = ["yandex", "bing", "google", "deepl", "alibaba"]

FROM_LANGUAGE = "auto"
TO_LANGUAGE = "ru"

INPUT_ENCODING = "utf-8"
OUTPUT_ENCODING = "utf-8"

LOG_LEVEL = logging.INFO
LOG_FORMAT = "%(asctime)s - %(levelname)s - %(message)s"

# ============================================================
# КОНФИГУРАЦИЯ ЛОГИРОВАНИЯ
# ============================================================

logging.basicConfig(
    level=LOG_LEVEL,
    format=LOG_FORMAT,
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("translation.log", encoding="utf-8")
    ]
)
logger = logging.getLogger(__name__)


# ============================================================
# ФУНКЦИИ РАЗБИЕНИЯ ТЕКСТА
# ============================================================

def split_into_chunks(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = OVERLAP_SIZE) -> list[str]:
    """
    Разбивает текст на чанки с указанным перекрытием.

    :param text: Исходный текст
    :param chunk_size: Размер чанка в символах
    :param overlap: Размер перекрытия между чанками
    :return: Список чанков текста
    """
    if not text:
        logger.warning("Получен пустой текст для разбиения")
        return []

    chunks = []
    start = 0
    text_length = len(text)

    while start < text_length:
        end = start + chunk_size
        chunk = text[start:end]
        chunks.append(chunk)
        
        logger.debug(f"Создан чанк {len(chunks)}: позиция {start}-{end}, длина {len(chunk)} символов")
        
        start = end - overlap
        
        if start >= text_length:
            break

    logger.info(f"Текст разбит на {len(chunks)} чанков (размер={chunk_size}, overlap={overlap})")
    return chunks


def merge_translations(translated_chunks: list[str], overlap: int = OVERLAP_SIZE) -> str:
    """
    Склеивает переведенные чанки, удаляя дублированные overlapped части.

    :param translated_chunks: Список переведенных чанков
    :param overlap: Размер перекрытия
    :return: Объединенный переведенный текст
    """
    if not translated_chunks:
        return ""

    if len(translated_chunks) == 1:
        return translated_chunks[0]

    result = translated_chunks[0]

    for i, chunk in enumerate(translated_chunks[1:], start=2):
        if overlap > 0 and len(chunk) > overlap:
            merged_part = result + chunk[overlap:]
        else:
            merged_part = result + chunk
        
        result = merged_part
        logger.debug(f"Склеен чанк {i}: общая длина {len(result)} символов")

    logger.info(f"Перевод склеен: итоговая длина {len(result)} символов")
    return result


# ============================================================
# ФУНКЦИИ ПЕРЕВОДА
# ============================================================

def translate_single_chunk(
    text: str,
    translator: str,
    from_lang: str = FROM_LANGUAGE,
    to_lang: str = TO_LANGUAGE
) -> str | None:
    """
    Переводит один чанк текста указанным переводчиком.

    :param text: Текст для перевода
    :param translator: Имя переводчика
    :param from_lang: Исходный язык
    :param to_lang: Целевой язык
    :return: Переведенный текст или None при ошибке
    """
    result_raw = None
    try:
        logger.debug(f"Перевод через {translator}: '{text[:50]}...'")
        
        result_raw = ts.translate_text(
            query_text=text,
            translator=translator,
            from_language=from_lang,
            to_language=to_lang
        )
        
        result = str(result_raw) if result_raw else None
        
        if result:
            logger.debug(f"Успешно переведено через {translator}: {len(result)} символов")
        return result

    except Exception as e:
        logger.warning(f"Ошибка перевода через {translator}: {e}")
        return None


def translate_with_fallback(
    text: str,
    translators_list: list[str] = TRANSLATORS_PRIORITY,
    from_lang: str = FROM_LANGUAGE,
    to_lang: str = TO_LANGUAGE,
    max_retries: int = MAX_RETRIES,
    retry_delay: int = RETRY_DELAY
) -> str | None:
    """
    Пытается перевести текст через список переводчиков с fallback.

    :param text: Текст для перевода
    :param translators_list: Список переводчиков в порядке приоритета
    :param from_lang: Исходный язык
    :param to_lang: Целевой язык
    :param max_retries: Максимальное количество попыток для одного переводчика
    :param retry_delay: Задержка между попытками в секундах
    :return: Переведенный текст или None, если все переводчики не работают
    """
    for translator in translators_list:
        logger.info(f"Попытка перевода через {translator}...")
        
        for attempt in range(1, max_retries + 1):
            logger.debug(f"Попытка {attempt}/{max_retries} через {translator}")
            
            result = translate_single_chunk(text, translator, from_lang, to_lang)
            
            if result:
                logger.info(f"Успешно переведено через {translator}")
                return result
            
            if attempt < max_retries:
                logger.warning(f"Неудачная попытка {attempt}, повтор через {retry_delay} сек...")
                time.sleep(retry_delay)
        
        logger.warning(f"Переводчик {translator} недоступен, пробуем следующий...")

    logger.error("Все переводчики недоступны")
    return None


def translate_text_advanced(
    text: str,
    chunk_size: int = CHUNK_SIZE,
    overlap: int = OVERLAP_SIZE,
    translators_list: list[str] = TRANSLATORS_PRIORITY,
    from_lang: str = FROM_LANGUAGE,
    to_lang: str = TO_LANGUAGE
) -> str | None:
    """
    Переводит большой текст чанками с перекрытием.

    :param text: Исходный текст
    :param chunk_size: Размер чанка
    :param overlap: Размер перекрытия
    :param translators_list: Список переводчиков
    :param from_lang: Исходный язык
    :param to_lang: Целевой язык
    :return: Переведенный текст или None при ошибке
    """
    logger.info(f"Начало перевода текста ({len(text)} символов)")
    
    chunks = split_into_chunks(text, chunk_size, overlap)
    
    if not chunks:
        logger.error("Не удалось разбить текст на чанки")
        return None
    
    translated_chunks = []
    total_chunks = len(chunks)
    
    for i, chunk in enumerate(chunks, start=1):
        logger.info(f"Перевод чанка {i}/{total_chunks} ({len(chunk)} символов)...")
        
        translated = translate_with_fallback(
            chunk,
            translators_list,
            from_lang,
            to_lang
        )
        
        if translated is None:
            logger.error(f"Не удалось перевести чанк {i}")
            return None
        
        translated_chunks.append(translated)
        logger.info(f"Чанк {i}/{total_chunks} переведен, получено {len(translated)} символов")
    
    result = merge_translations(translated_chunks, overlap)
    
    logger.info(f"Перевод завершен: всего обработано {total_chunks} чанков, результат {len(result)} символов")
    return result


# ============================================================
# CLI ИНТЕРФЕЙС
# ============================================================

def parse_arguments():
    """Парсит аргументы командной строки."""
    parser = argparse.ArgumentParser(
        description="Перевод больших текстовых файлов с использованием библиотеки translators",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры использования:
  python translate_cli.py input.txt -o output.txt
  python translate_cli.py input.txt --to-language es
  python translate_cli.py input.txt --chunk-size 5000 --overlap 300
  python translate_cli.py input.txt --translators yandex bing google
        """
    )
    
    parser.add_argument(
        "input_file",
        type=str,
        help="Путь к входному файлу с текстом"
    )
    
    parser.add_argument(
        "-o", "--output",
        type=str,
        default=None,
        help="Путь к выходному файлу (по умолчанию: input_translated.txt)"
    )
    
    parser.add_argument(
        "--from-language",
        type=str,
        default=FROM_LANGUAGE,
        help=f"Исходный язык (по умолчанию: {FROM_LANGUAGE})"
    )
    
    parser.add_argument(
        "--to-language",
        type=str,
        default=TO_LANGUAGE,
        help=f"Целевой язык (по умолчанию: {TO_LANGUAGE})"
    )
    
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=CHUNK_SIZE,
        help=f"Размер чанка в символах (по умолчанию: {CHUNK_SIZE})"
    )
    
    parser.add_argument(
        "--overlap",
        type=int,
        default=OVERLAP_SIZE,
        help=f"Размер перекрытия между чанками (по умолчанию: {OVERLAP_SIZE})"
    )
    
    parser.add_argument(
        "--translators",
        type=str,
        nargs="+",
        default=TRANSLATORS_PRIORITY,
        help="Список переводчиков в порядке приоритета"
    )
    
    parser.add_argument(
        "--max-retries",
        type=int,
        default=MAX_RETRIES,
        help=f"Максимальное количество попыток (по умолчанию: {MAX_RETRIES})"
    )
    
    parser.add_argument(
        "--retry-delay",
        type=int,
        default=RETRY_DELAY,
        help=f"Задержка между попытками в секундах (по умолчанию: {RETRY_DELAY})"
    )
    
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Включить подробное логирование (DEBUG)"
    )
    
    parser.add_argument(
        "--list-translators",
        action="store_true",
        help="Показать список доступных переводчиков и выйти"
    )
    
    return parser.parse_args()


def list_available_translators():
    """Выводит список доступных переводчиков в библиотеке."""
    print("\nAvailable translators in translators library:")
    print("-" * 50)
    
    available = []
    test_text = "Hello"
    
    for translator in TRANSLATORS_PRIORITY:
        try:
            result = ts.translate_text(test_text, translator=translator, to_language="ru")
            if result:
                available.append(translator)
                print(f"  [OK] {translator}")
        except Exception:
            print(f"  [FAIL] {translator}")
    
    print(f"\nРаботают: {', '.join(available)}")
    print(f"Всего доступно: {len(available)}")


# ============================================================
# MAIN
# ============================================================

def main():
    """Основная функция."""
    args = parse_arguments()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
        logger.debug("Включен подробный режим логирования")
    
    if args.list_translators:
        list_available_translators()
        return
    
    input_path = Path(args.input_file)
    
    if not input_path.exists():
        logger.error(f"Файл не найден: {input_path}")
        sys.exit(1)
    
    output_path = Path(args.output) if args.output else input_path.with_name(
        input_path.stem + "_translated.txt"
    )
    
    logger.info(f"Чтение файла: {input_path}")
    
    try:
        with open(input_path, "r", encoding=INPUT_ENCODING) as f:
            text = f.read()
    except Exception as e:
        logger.error(f"Ошибка чтения файла: {e}")
        sys.exit(1)
    
    logger.info(f"Прочитано {len(text)} символов из файла")
    logger.info(f"Параметры: from={args.from_language}, to={args.to_language}")
    logger.info(f"Чанки: размер={args.chunk_size}, overlap={args.overlap}")
    logger.info(f"Переводчики: {args.translators}")
    
    start_time = time.time()
    
    result = translate_text_advanced(
        text=text,
        chunk_size=args.chunk_size,
        overlap=args.overlap,
        translators_list=args.translators,
        from_lang=args.from_language,
        to_lang=args.to_language
    )
    
    if result is None:
        logger.error("Перевод не выполнен из-за ошибок")
        sys.exit(1)
    
    elapsed_time = time.time() - start_time
    
    try:
        with open(output_path, "w", encoding=OUTPUT_ENCODING) as f:
            f.write(result)
        
        logger.info(f"Результат сохранен в: {output_path}")
        logger.info(f"Длина перевода: {len(result)} символов")
        logger.info(f"Время выполнения: {elapsed_time:.2f} секунд")
        
    except Exception as e:
        logger.error(f"Ошибка сохранения файла: {e}")
        sys.exit(1)
    
    print(f"\n[OK] Translation completed successfully!")
    print(f"  Input file: {input_path}")
    print(f"  Output file: {output_path}")
    print(f"  Source size: {len(text)} symbols")
    print(f"  Translated: {len(result)} symbols")
    print(f"  Time: {elapsed_time:.2f} sec")


if __name__ == "__main__":
    main()
