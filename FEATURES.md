# Реализованная функциональность

Дата фиксации: 2026-11-14.

## Живые субтитры UN Web TV

- Распаковываемое Chrome Manifest V3 расширение в `extension/`.
- Предварительная обработка аудио HLS и показ фраз по `video.currentTime`.
- Загрузка HLS окнами до 9 сегментов; ASR-блоки обрабатываются конвейером
  с ограниченной очередью.
- Первый блок — 30 секунд аудио, поэтому субтитры можно показывать почти сразу;
  каждый готовый блок сохраняется и сразу передаётся расширению по WebSocket,
  не дожидаясь конца записи.
- Переключение локального WhisperX и облачного OpenAI-совместимого ASR.
- Локальный перевод фраз: движки `opus` (Helsinki-NLP opus-mt-en-ru через
  transformers) и `argos` (Argos Translate); язык перевода пока `ru`.
- Озвучка субтитров: браузерный `speechSynthesis` или Edge TTS (mp3 с
  дисковым кешем в `video/tts/`); источник — перевод или оригинал; громкость
  видео приглушается на время реплики.
- API: `GET /api/videos/live-transcription/health`,
  `POST /api/videos/captions/prepare`, `GET/WS /api/videos/captions/jobs/{job_id}`,
  `GET /api/videos/captions/media/{asset_key}`,
  `GET /api/videos/captions/tts/voices`, `GET /api/videos/captions/tts/audio`.
- FLAC-аудио и таймкодированные результаты хранятся без срока в SQLite и
  `video/captions/`; повторная подготовка переиспользует кеш.
- Установка и настройка описаны в `extension/README.md`.

## Расписание и метаданные

- `schedule_parser.py` — парсинг расписания UN WebTV за день и период.
- `parser.py` — парсинг страницы видео: заголовок, описание, языки, дата
  производства, длительность, категории, транскрипт.
- REST: `GET /api/schedule/{date}`, `GET /api/schedule?start_date=&end_date=`,
  `POST /api/schedule/save`.
- CLI: `copy_urls.py`, `copy_urls_file_class.py`.

## База данных

- SQLite-схема: `videos`, `download_logs`, `transcriptions`.
- CRUD для видео, транскрипций и логов в `database.py`.
- Статусы видео: `new`, `downloaded`, `partial`, `transcribed`, `uploading`,
  `upload_failed`.
- CLI: `add_to_db.py url|dir|list`.

## Скачивание видео

- Поиск HLS-URL через Selenium performance log.
- Скачивание сегментов `seg-N-v1-a1.ts` через ffmpeg.
- Проверка целостности сегментов через ffprobe.
- Продолжение загрузки с последнего валидного сегмента.
- Склейка сегментов в `output.ts`.
- Остановка фоновой загрузки через `threading.Event`.
- REST: `/api/videos/{id}/download`, `/download/stop`, `/concat`,
  `/segments-info`.
- CLI: `download_cli.py`.

## Транскрипты

- Извлечение готового транскрипта со страницы UN WebTV
  (`transcript_extractor.py`).
- Транскрибация видео через WhisperX (`transcriber.py`, опционально).
- Суммаризация, перевод и ключевые слова через OpenAI-совместимый API
  (`summarizer.py`).
- Перевод больших текстов чанками (`translate_cli.py`).
- REST: `/api/videos/{id}/transcript`, `/transcribe`.
- CLI: `transcribe_cli.py transcribe|summarize|pipeline`.

## Rutube

- Авторизация и сохранение cookies.
- Загрузка файла с заголовком, описанием и тегами.
- Загрузка видео из БД по ID с обновлением статуса и URL.
- CLI: `rutube_cli.py login|upload|upload-db`.

## Web-интерфейс

- Загрузка расписания за период.
- Таблица видео с фильтрацией и действиями.
- Запуск/остановка загрузки, склейка, транскрибация.
- Просмотр логов и транскриптов.
- Потоковое воспроизведение и открытие папки с файлом.

## Ограничения

- Автоматических тестов и CI нет.
- Фоновые задачи выполняются в потоках процесса API.
- Нет аутентификации и разграничения доступа.
- Часть модулей превышает лимиты AGENTS.md; см. `docs/ARCHITECTURE.md`.

## Следующие шаги

1. Покрыть тестами парсеры, `Database` и сервисы.
2. Разделить `database.py` на репозитории.
3. Вынести Selenium/ffmpeg/HTTP-клиенты в инфраструктурный слой.
4. Заменить потоки на очередь задач.
5. Добавить аутентификацию и закрыть CORS для production.
