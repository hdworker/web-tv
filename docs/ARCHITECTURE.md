# Архитектура проекта

Документ описывает текущее устройство кодовой базы и целевое направление рефакторинга.
Правила разработки и ограничения по размеру файлов/функций — в `../AGENTS.md`.

## 1. Назначение

Платформа автоматизирует полный цикл работы с видео UN WebTV:

1. получить расписание и ссылки на видео;
2. сохранить метаданные видео в SQLite;
3. скачать HLS-сегменты и склеить их в один файл;
4. извлечь или распознать транскрипт;
5. сделать перевод и краткое резюме;
6. загрузить видео на Rutube;
7. управлять процессом через REST API и web-интерфейс.

## 2. Текущая архитектура

### 2.1. Точка входа и конфигурация

- `main.py` — создаёт FastAPI-приложение, настраивает логирование, CORS,
  middleware логирования запросов и подключает роутеры.
- `config.py` — читает `config.json` из рабочего каталога; значения по умолчанию
  задаются в классе `Config`.
- `config.example.json` — шаблон локальной конфигурации.

### 2.2. API-слой

```text
main.py
└── api/schedule.py          # /api/schedule
└── api/main.py              # /api/videos
    ├── api/endpoints/read.py
    ├── api/endpoints/create.py
    ├── api/endpoints/download.py
    ├── api/endpoints/transcribe.py
    ├── api/endpoints/caption_preparation.py
    └── api/endpoints/utils.py
```

- `api/models.py` — Pydantic-модели запросов и ответов.
- `api/state.py` — словарь состояний фоновых загрузок (`threading.Event`).
- `api/services/` — сервисы чтения транскрипта и информации о сегментах.
- Фоновые операции загрузки, склейки и транскрибации запускаются в отдельных
  потоках внутри процесса API. Прогресс задачи хранится в памяти процесса;
  завершённые субтитры и метаданные FLAC сохраняются в SQLite.

### 2.3. Прикладные модули

| Модуль | Ответственность |
|---|---|
| `parser.py` | Разбор страницы видео UN WebTV: заголовок, описание, языки, категории, транскрипт |
| `schedule_parser.py` | Разбор страницы расписания за день и период |
| `downloader.py` | Selenium: поиск HLS-URL; ffmpeg: скачивание, проверка и склейка сегментов |
| `transcript_extractor.py` | Selenium/requests + BeautifulSoup: извлечение транскрипта |
| `transcriber.py` | WhisperX: извлечение аудио, распознавание, выравнивание, диаризация |
| `api/services/caption_pipeline.py` | Выбор сохранённого FLAC или конвейера загрузки |
| `api/services/caption_stream.py` | Consumer: ASR-блоки по порядку одной моделью |
| `api/services/caption_stream_producer.py` | Producer: окна HLS → очередь блоков → FLAC |
| `api/services/caption_segmenter.py` | Параллельная загрузка окон аудиосегментов с таймкодами |
| `api/services/caption_identity.py` | Канонический asset URL и ключ кеша ASR/перевода |
| `api/services/caption_jobs.py` | Очередь подготовки и сохранение cues |
| `api/services/caption_job_state.py` | Состояние задач в памяти процесса |
| `api/services/caption_job_callbacks.py` | Колбэки прогресса и частичных блоков |
| `api/services/translation_engines.py` | Локальный перевод фраз: opus-mt и Argos |
| `api/services/tts_edge.py` | Синтез Edge TTS с кешем mp3 и перебором голосов |
| `summarizer.py` | OpenAI-совместимый HTTP-клиент: суммаризация, перевод, ключевые слова |
| `rutube.py` | Selenium: авторизация, cookies, загрузка видео и метаданных на Rutube |
| `database.py` | SQLite: датаклассы `Video`, `Transcription`, `DownloadLog` и CRUD |
| `video_download_service.py` | Задел на сервисный слой управления загрузкой |

### 2.4. CLI-утилиты

- `copy_urls.py` — расписание → `video_links_<date>.csv`.
- `copy_urls_file_class.py` — CSV со ссылками → Excel с метаданными.
- `download_cli.py` — скачивание одного видео или списка за дату.
- `add_to_db.py` — добавление видео в БД по URL/каталогу, просмотр списка.
- `transcribe_cli.py` — транскрибация, суммаризация, полный pipeline.
- `rutube_cli.py` — вход, загрузка файла или видео из БД.
- `translate_cli.py` — перевод больших текстов чанками через `translators`.

### 2.5. Frontend

```text
frontend/src
├── api.js                 # axios-клиент REST API
├── pages/HomePage.jsx     # компоновка страницы
├── components/
│   ├── ScheduleForm.jsx   # загрузка расписания за период
│   ├── VideoTable.jsx     # таблица видео и действия
│   ├── LogModal.jsx       # логи фоновых операций
│   └── TranscriptModal.jsx# просмотр транскрипта
└── i18n/ru.js             # тексты интерфейса
```

Vite проксирует `/api` на `http://localhost:8000`. Frontend не встраивается в
FastAPI и запускается отдельно в режиме разработки; production-сборка лежит в
`frontend/dist` и в репозиторий не коммитится.

## 3. Потоки данных

### 3.1. Расписание

```text
GET /api/schedule/{date}
  → schedule_parser.get_schedule()
  → requests + BeautifulSoup
  → список dict-элементов
```

```text
POST /api/schedule/save
  → schedule_parser.get_schedule_period()
  → Database.add_video()
  → un_videos.db
```

### 3.2. Загрузка видео

```text
POST /api/videos/{id}/download
  → threading.Thread
  → VideoDownloader.download_full()
      → Selenium: перехват HLS-запроса
      → ffmpeg: seg-N-v1-a1.ts
      → ffprobe: проверка целостности
      → ffmpeg concat: output.ts
  → Database.update_video(status="downloaded")
  → download_logs
```

### 3.3. Транскрипт

```text
GET /api/videos/{id}/transcript
  → transcript_service.get_transcript()
      → есть текст в БД? вернуть из БД
      → иначе transcript_extractor.extract_transcript_from_url()
          → Selenium/requests + BeautifulSoup
          → Database.add_transcription()
```

### 3.4. Транскрибация и суммаризация

```text
POST /api/videos/{id}/transcribe
  → VideoTranscriber.extract_audio()  (ffmpeg)
  → WhisperX: transcribe + align
  → Database.add_transcription()
  → TextSummarizer.summarize()        (OpenAI-совместимый API)
```

### 3.5. Rutube

```text
python rutube_cli.py login|upload|upload-db
  → RutubeUploader
      → Selenium: cookies / форма загрузки
      → rutube_cookies.json
      → Database.update_video(rutube_video_url=...)
```

### 3.6. Синхронизированные субтитры

```text
POST /api/videos/captions/prepare
  → canonical asset + ключ ASR
  → live_stream=false:
      → cache hit с FLAC? вернуть сохранённые cues
      → иначе фоновая numbered HLS/VOD задача (прежний путь)
          → до 9 сегментов загружаются параллельно
          → первый ASR-блок ~30 с, далее блоки ~2 мин
          → ограниченная очередь ASR-блоков
              → пока один блок распознаётся, следующие сегменты загружаются
          → временная склейка TS → FLAC → WAV для ASR
          → cues сохраняются и публикуются по мере готовности блоков
  → live_stream=true:
      → отдельный cache key, поиск авторизованного HLS master playlist
      → выбор английской аудио-вариации; FFmpeg пишет 12-секундные WAV блоки
      → WhisperX/OpenAI ASR → cues с таймкодом от начала захвата
      → stop route завершает FFmpeg; cues сохраняются при остановке
      → подписанные URL не сохраняются
  → при включённом переводе блок переводится до публикации
      (движок opus или argos, поле translation рядом с text)
  → WS /api/videos/captions/jobs/{job_id}/ws
  → extension: VOD cues по video.currentTime; live — последние три фразы
      → браузерный speechSynthesis или mp3 из /captions/tts/audio
      → громкость видео приглушается на время реплики
```

## 4. Модель данных SQLite

Таблица `videos`:

- `id`, `date`, `source_date`, `un_video_url` (UNIQUE);
- `local_video_path`, `rutube_video_id`, `rutube_video_url`;
- `title`, `description`, `category`, `thumbnail`, `tags`;
- `broadcasting_entity`, `duration`, `languages`, `status`;
- `created_at`, `updated_at`.

Таблица `download_logs`:

- `id`, `video_id`, `action`, `log_text`, `status`, `created_at`.

Таблица `transcriptions`:

- `id`, `video_id`, `language`, `transcript_text`, `summary_text`;
- `created_at`, `updated_at`.

Таблица `caption_media`:

- `asset_key`, канонический `video_url`, путь к FLAC;
- формат, длительность, размер файла и даты создания/обновления.

Таблица `caption_caches`:

- ключ кеша, `asset_key`, режим/модель ASR, язык;
- `cues_json` с временными метками фраз и дата создания;
- `is_complete`: 0 — блоки ещё дозаписываются, 1 — транскрипт готов.

FLAC-файлы хранятся в `video/captions/` без автоматического срока удаления.
Временные TS/WAV-файлы удаляются после подготовки. Ключ кеша учитывает URL,
режим, модель, язык и версию pipeline.

Статусы видео: `new`, `downloaded`, `partial`, `transcribed`, `uploading`,
`upload_failed`.

## 5. Ограничения текущей реализации

1. Нет автоматических тестов и CI.
2. Файлы `database.py`, `downloader.py`, `rutube.py`, `main.py` и `translate_cli.py`
   превышают целевой лимит 150 строк; часть функций длиннее 30 строк.
3. Активные задачи живут в потоках процесса API: при перезапуске прогресс
   теряется; сохранённые cues и FLAC-архивы остаются доступны в SQLite/на диске.
4. API без аутентификации, CORS `*`; предполагается локальный/внутренний контур.
5. Selenium-селекторы зависят от вёрстки UN WebTV и Rutube.
6. WhisperX и ffmpeg — внешние системные зависимости; модель `large-v3` тяжёлая.
7. `video_download_service.py` и `api/services/` частично дублируют логику
   `api/endpoints/download.py`.

## 6. Целевая архитектура

Направление рефакторинга — разделить слои и уменьшить связанность:

```text
api/            HTTP-роуты, валидация, зависимости
services/       бизнес-логика и оркестрация
repositories/   CRUD по сущностям (Video, Transcription, DownloadLog)
infrastructure/ Selenium, ffmpeg, Rutube, OpenAI, WhisperX
models/         датаклассы и Pydantic-модели
utils/          файлы, логирование, валидаторы
```

Порядок миграции:

1. вынести репозитории из `database.py`, сохранив публичный интерфейс `Database`;
2. выделить `VideoDownloadService`, `TranscriptService`, `RutubeUploadService`;
3. инкапсулировать Selenium/ffmpeg/HTTP-клиенты в `infrastructure/`;
4. заменить фоновые потоки на очередь задач;
5. добавить unit- и интеграционные тесты;
6. обновить `AGENTS.md`, `FEATURES.md` и этот документ.

## 7. Контракты сервисов (целевые)

```python
class VideoDownloadService:
    def download(self, video_url: str, stop_event=None) -> tuple[bool, str | None]:
        """Скачивает видео по URL UN WebTV и возвращает путь к результату."""

class VideoRepository:
    def get_by_id(self, video_id: int) -> Video | None:
        """Возвращает видео по ID или None."""

class RutubeClient:
    def upload_video(self, file_path: str, title: str, description: str) -> tuple[bool, str | None]:
        """Загружает видео на Rutube и возвращает URL публикации."""

class TranscriptExtractor:
    def extract_from_url(self, url: str, use_selenium: bool = True) -> str:
        """Извлекает транскрипт со страницы UN WebTV."""
```

## 8. Метрики успеха рефакторинга

- 0 файлов длиннее 150 строк, 0 функций длиннее 30 строк.
- 100% публичных функций имеют docstring на русском языке.
- Ключевые сценарии работают без регрессий и замедления более чем на 10%.
- Появляются тесты на парсинг, БД и сервисы.
- Фоновые задачи можно перезапускать и масштабировать независимо от API.
