# UN WebTV Video Platform

Платформа для работы с видео с [UN WebTV](https://webtv.un.org): получение расписания,
скачивание видео, транскрибация, суммаризация и публикация на Rutube.

Репозиторий содержит только исходный код проекта: backend на FastAPI, CLI-утилиты и
frontend на React + Vite. Базы данных, скачанные видео, cookies, логи и отладочные дампы
в репозиторий не входят.

## Возможности

- Получение расписания UN WebTV за день или период.
- Сохранение расписания и видео в SQLite.
- Скачивание HLS-сегментов видео через Selenium + ffmpeg с продолжением загрузки.
- Склейка сегментов в единый `.ts`-файл.
- Извлечение транскрипта со страницы UN WebTV.
- Транскрибация видео через WhisperX (опционально).
- Суммаризация, перевод и извлечение ключевых слов через OpenAI-совместимый API.
- Загрузка видео на Rutube через Selenium.
- Web-интерфейс для управления расписанием, загрузкой, транскриптами и логами.
- REST API с документацией Swagger/ReDoc.

## Структура репозитория

```text
.
├── main.py                     # Точка входа FastAPI, middleware, корневая страница
├── config.py                   # Загрузка config.json / переменных окружения
├── database.py                 # SQLite: видео, транскрипции, логи
├── parser.py                   # Парсер страниц видео и расписания UN WebTV
├── schedule_parser.py          # Парсер расписания за день/период
├── downloader.py               # Selenium + ffmpeg: скачивание и склейка сегментов
├── transcript_extractor.py     # Извлечение транскрипта со страницы
├── transcriber.py              # WhisperX: транскрибация видео
├── summarizer.py               # OpenAI-совместимый клиент: суммаризация и перевод
├── rutube.py                   # Selenium-загрузчик на Rutube
├── video_download_service.py   # Сервис управления загрузкой (задел на рефакторинг)
├── api/
│   ├── main.py                 # Роутер /api/videos
│   ├── schedule.py             # Роутер /api/schedule
│   ├── models.py               # Pydantic-модели
│   ├── state.py                # Состояние фоновых загрузок
│   ├── endpoints/              # read, create, download, transcribe, utils
│   └── services/               # transcript_service, video_service
├── frontend/                   # React 19 + Vite + Ant Design
│   ├── src/
│   │   ├── api.js              # Клиент REST API
│   │   ├── pages/              # HomePage
│   │   ├── components/         # ScheduleForm, VideoTable, LogModal, TranscriptModal
│   │   └── i18n/ru.js          # Русские подписи
│   ├── package.json
│   └── vite.config.js          # Прокси /api -> http://localhost:8000
├── docs/ARCHITECTURE.md        # Целевая архитектура и план рефакторинга
├── AGENTS.md                   # Правила разработки для команды и LLM-агентов
├── requirements.txt
└── config.example.json
```

## Требования

- Python 3.10+ (проект проверен на Python 3.12).
- Node.js 18+ и npm.
- ffmpeg и ffprobe в `PATH` — используются для скачивания, проверки и склейки видео.
- Google Chrome — для Selenium.
- Опционально: WhisperX и torch для локальной транскрибации.
- Опционально: доступ к OpenAI-совместимому API для суммаризации и перевода.

## Быстрый старт

### 1. Backend

```bash
py -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

pip install -r requirements.txt

# Windows:
copy config.example.json config.json
# Linux/macOS:
cp config.example.json config.json

uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

Альтернативный запуск: `python main.py` — приложение само выберет свободный порт
начиная с 8000 и выведет адрес в консоль.

После запуска:

- `http://127.0.0.1:8000/` — страница с описанием API;
- `http://127.0.0.1:8000/docs` — Swagger UI;
- `http://127.0.0.1:8000/redoc` — ReDoc.

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

Vite запустится на `http://localhost:5173` и проксирует запросы `/api` на
`http://localhost:8000`. Backend должен быть запущен на порту 8000.

Production-сборка:

```bash
npm run build
```

Содержимое `frontend/dist/` — артефакт сборки, в репозиторий не коммитится.

### 3. Опциональные компоненты

Транскрибация через WhisperX:

```bash
pip install whisperx
```

Модель `large-v3` загружается при первом запуске и требует много памяти и диска.
По умолчанию используется CPU, поэтому обработка длинных видео может быть медленной.

Суммаризация и перевод используют переменные окружения:

| Переменная | Назначение | Значение по умолчанию |
|---|---|---|
| `OPENAI_API_KEY` | Ключ OpenAI-совместимого API | пусто (функции отключены) |
| `OPENAI_URL` | Базовый URL API | `https://bothub.chat/api/v2/openai/v1` |
| `OPENAI_MODEL` | Модель | `gpt-4o-mini` |
| `DEV` | Режим разработки | `false` |

## Конфигурация

`config.py` читает `config.json` из текущего каталога. Если файла нет, используются
значения по умолчанию. Пример:

```json
{
  "dev": true,
  "log_requests": true,
  "log_responses": true,
  "log_level": "DEBUG"
}
```

`config.json` не коммитится. Для локальной настройки скопируйте
`config.example.json` в `config.json`.

## CLI

### Расписание и экспорт

```bash
# Скачать список ссылок за дату в video_links_YYYY-MM-DD.csv
python copy_urls.py 2025-04-02

# Собрать метаданные по ссылкам из CSV и сохранить в Excel
python copy_urls_file_class.py 2025-04-02
```

### Скачивание видео

```bash
# Одно видео по URL
python download_cli.py "https://webtv.un.org/en/asset/..."

# Все видео из video_links_YYYY-MM-DD.csv
python download_cli.py --date 2025-04-02

# Headless-режим и без склейки сегментов
python download_cli.py "https://webtv.un.org/en/asset/..." --headless --no-concat
```

### Работа с базой данных

```bash
python add_to_db.py url "https://webtv.un.org/en/asset/..." "video/asset/output.ts"
python add_to_db.py dir video/asset --url "https://webtv.un.org/en/asset/..."
python add_to_db.py list --status downloaded --limit 20
```

### Транскрибация и суммаризация

```bash
python transcribe_cli.py transcribe video.ts --lang en --video-id 1
python transcribe_cli.py summarize transcript.txt --translate ru --video-id 1
python transcribe_cli.py pipeline video.ts --video-id 1 --output-dir video/asset
```

### Rutube

```bash
python rutube_cli.py login USERNAME PASSWORD
python rutube_cli.py upload video.ts --title "Заголовок" --description "Описание"
python rutube_cli.py upload-db 1
```

Cookies сохраняются в `rutube_cookies.json` и не должны попадать в репозиторий.

### Перевод больших текстов

```bash
python translate_cli.py transcript.txt -o transcript_ru.txt --to-language ru
python translate_cli.py --list-translators
```

## REST API

| Метод | Путь | Назначение |
|---|---|---|
| GET | `/api/schedule/{date}` | Расписание на дату (`YYYY-MM-DD`) |
| GET | `/api/schedule?start_date=&end_date=` | Расписание за период |
| POST | `/api/schedule/save?start_date=&end_date=` | Сохранить расписание в БД |
| GET | `/api/videos?status=&limit=` | Список видео |
| GET | `/api/videos/{id}` | Видео по ID |
| POST | `/api/videos` | Добавить видео |
| POST | `/api/videos/{id}/download` | Запустить загрузку |
| POST | `/api/videos/{id}/download/stop` | Остановить загрузку |
| POST | `/api/videos/{id}/concat` | Склеить сегменты |
| POST | `/api/videos/{id}/transcribe` | Запустить транскрибацию |
| GET | `/api/videos/{id}/logs` | Логи видео |
| GET | `/api/videos/{id}/details` | Обновить метаданные со страницы UN |
| GET | `/api/videos/{id}/transcript` | Получить транскрипт |
| POST | `/api/videos/{id}/open-folder` | Открыть папку с видео |
| GET | `/api/videos/{id}/stream` | Потоковое воспроизведение |
| GET | `/api/videos/{id}/segments-info` | Информация о сегментах |

## Данные и артефакты

Во время работы создаются файлы, которые не входят в репозиторий:

- `un_videos.db` — SQLite-база;
- `video/<uuid>/` — сегменты `seg-*.ts` и `output.ts`;
- `rutube_cookies.json` — cookies авторизации Rutube;
- `translation.log`, `transcript.txt`, `summary.txt` — результаты операций;
- `config.json` — локальная конфигурация.

Все перечисленные пути добавлены в `.gitignore`.

## Текущее состояние и ограничения

- Автоматических тестов пока нет; проверка выполняется запуском CLI и API вручную.
- Часть модулей превышает целевые лимиты AGENTS.md (150 строк на файл, 30 строк на
  функцию). План рефакторинга — в `docs/ARCHITECTURE.md`.
- Загрузка и транскрибация выполняются в фоновых потоках процесса FastAPI. Для
  production-нагрузки рекомендуется вынести их в очередь задач (Celery/RQ).
- API не имеет аутентификации, CORS открыт для всех источников. Рассчитан на локальный
  или внутренний контур; перед публикацией в интернет нужен reverse proxy и авторизация.
- Selenium-сценарии зависят от вёрстки UN WebTV и Rutube; при изменениях сайтов
  селекторы могут потребовать обновления.
- WhisperX и ffmpeg требуют отдельных системных зависимостей.

## Правила разработки

Правила проекта, требования к docstring, структуре модулей и рабочий процесс описаны
в `AGENTS.md`. Перед значимыми изменениями ознакомьтесь с ним и с
`docs/ARCHITECTURE.md`.

## Безопасность

Не коммитьте в репозиторий:

- `config.json`, `.env`, ключи API;
- `rutube_cookies.json`, `token.json`, `credentials.json`;
- базы данных, видео, транскрипты и логи;
- отладочные дампы страниц и сетевых запросов.

Для секретов используйте переменные окружения или локальные файлы из `.gitignore`.
