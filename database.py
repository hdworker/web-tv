import sqlite3
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, asdict
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class Video:
    id: Optional[int] = None
    date: str = ""
    source_date: str = ""
    un_video_url: str = ""
    local_video_path: Optional[str] = None
    rutube_video_id: Optional[str] = None
    rutube_video_url: Optional[str] = None
    title: str = ""
    description: str = ""
    category: str = ""
    thumbnail: str = ""
    tags: str = ""
    broadcasting_entity: str = ""
    duration: str = ""
    languages: str = ""
    status: str = "new"
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


@dataclass
class DownloadLog:
    id: Optional[int] = None
    video_id: int = 0
    action: str = ""
    log_text: str = ""
    status: str = "pending"
    created_at: Optional[str] = None


@dataclass
class Transcription:
    id: Optional[int] = None
    video_id: int = 0
    language: str = ""
    transcript_text: str = ""
    summary_text: str = ""
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class Database:
    def __init__(self, db_path: str = "un_videos.db"):
        self.db_path = db_path
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS videos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT,
                source_date TEXT,
                un_video_url TEXT UNIQUE,
                local_video_path TEXT,
                rutube_video_id TEXT,
                rutube_video_url TEXT,
                title TEXT,
                description TEXT,
                category TEXT,
                thumbnail TEXT,
                tags TEXT,
                broadcasting_entity TEXT,
                duration TEXT,
                languages TEXT,
                status TEXT DEFAULT 'new',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS download_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                video_id INTEGER REFERENCES videos(id) ON DELETE CASCADE,
                action TEXT,
                log_text TEXT,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS transcriptions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                video_id INTEGER REFERENCES videos(id) ON DELETE CASCADE,
                language TEXT,
                transcript_text TEXT,
                summary_text TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.commit()
        conn.close()
        logger.info(f"База данных инициализирована: {self.db_path}")

    def add_video(self, video: Video) -> Optional[int]:
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO videos (
                date, source_date, un_video_url, local_video_path, rutube_video_id,
                rutube_video_url, title, description, category, thumbnail, tags,
                broadcasting_entity, duration, languages, status
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            video.date, video.source_date, video.un_video_url, video.local_video_path,
            video.rutube_video_id, video.rutube_video_url,
            video.title, video.description, video.category, video.thumbnail, video.tags,
            video.broadcasting_entity, video.duration, video.languages, video.status
        ))

        video_id: int = cursor.lastrowid  # type: ignore
        conn.commit()
        conn.close()
        logger.info(f"Видео добавлено с ID: {video_id}")
        return video_id if video_id else None

    def get_video(self, video_id: int) -> Optional[Video]:
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM videos WHERE id = ?", (video_id,))
        row = cursor.fetchone()
        conn.close()

        if row:
            return Video(
                id=row["id"],
                date=row["date"],
                source_date=row["source_date"],
                un_video_url=row["un_video_url"],
                local_video_path=row["local_video_path"],
                rutube_video_id=row["rutube_video_id"],
                rutube_video_url=row["rutube_video_url"],
                title=row["title"],
                description=row["description"],
                category=row["category"],
                thumbnail=row["thumbnail"],
                tags=row["tags"],
                broadcasting_entity=row["broadcasting_entity"],
                duration=row["duration"],
                languages=row["languages"],
                status=row["status"],
                created_at=row["created_at"],
                updated_at=row["updated_at"]
            )
        return None

    def get_video_by_url(self, url: str) -> Optional[Video]:
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM videos WHERE un_video_url = ?", (url,))
        row = cursor.fetchone()
        conn.close()

        if row:
            return Video(
                id=row["id"],
                date=row["date"],
                source_date=row["source_date"],
                un_video_url=row["un_video_url"],
                local_video_path=row["local_video_path"],
                rutube_video_id=row["rutube_video_id"],
                rutube_video_url=row["rutube_video_url"],
                title=row["title"],
                description=row["description"],
                category=row["category"],
                thumbnail=row["thumbnail"],
                tags=row["tags"],
                broadcasting_entity=row["broadcasting_entity"],
                duration=row["duration"],
                languages=row["languages"],
                status=row["status"],
                created_at=row["created_at"],
                updated_at=row["updated_at"]
            )
        return None

    def update_video(self, video_id: int, **kwargs) -> bool:
        allowed_fields = [
            "date", "source_date", "local_video_path", "rutube_video_id", "rutube_video_url",
            "title", "description", "category", "thumbnail", "tags", "broadcasting_entity",
            "duration", "languages", "status"
        ]

        fields = {k: v for k, v in kwargs.items() if k in allowed_fields}
        if not fields:
            return False

        fields["updated_at"] = datetime.now().isoformat()

        set_clause = ", ".join([f"{k} = ?" for k in fields.keys()])
        values = list(fields.values()) + [video_id]

        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(f"UPDATE videos SET {set_clause} WHERE id = ?", values)
        conn.commit()
        conn.close()

        logger.info(f"Видео {video_id} обновлено")
        return True

    def get_videos(self, status: Optional[str] = None, limit: int = 100) -> List[Video]:
        conn = self._get_connection()
        cursor = conn.cursor()

        if status:
            cursor.execute("SELECT * FROM videos WHERE status = ? LIMIT ?", (status, limit))
        else:
            cursor.execute("SELECT * FROM videos LIMIT ?", (limit,))

        rows = cursor.fetchall()
        conn.close()

        videos = []
        for row in rows:
            videos.append(Video(
                id=row["id"],
                date=row["date"],
                source_date=row["source_date"],
                un_video_url=row["un_video_url"],
                local_video_path=row["local_video_path"],
                rutube_video_id=row["rutube_video_id"],
                rutube_video_url=row["rutube_video_url"],
                title=row["title"],
                description=row["description"],
                category=row["category"],
                thumbnail=row["thumbnail"],
                tags=row["tags"],
                broadcasting_entity=row["broadcasting_entity"],
                duration=row["duration"],
                languages=row["languages"],
                status=row["status"],
                created_at=row["created_at"],
                updated_at=row["updated_at"]
            ))
        return videos

    def delete_video(self, video_id: int) -> bool:
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM videos WHERE id = ?", (video_id,))
        conn.commit()
        conn.close()
        logger.info(f"Видео {video_id} удалено")
        return True

    def add_transcription(self, transcription: Transcription) -> Optional[int]:
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO transcriptions (
                video_id, language, transcript_text, summary_text
            ) VALUES (?, ?, ?, ?)
        """, (
            transcription.video_id, transcription.language,
            transcription.transcript_text, transcription.summary_text
        ))

        transcription_id = cursor.lastrowid
        conn.commit()
        conn.close()
        logger.info(f"Транскрипция добавлена с ID: {transcription_id}")
        return transcription_id if transcription_id else 0

    def get_transcriptions(self, video_id: int) -> List[Transcription]:
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM transcriptions WHERE video_id = ?",
            (video_id,)
        )

        rows = cursor.fetchall()
        conn.close()

        transcriptions = []
        for row in rows:
            transcriptions.append(Transcription(
                id=row["id"],
                video_id=row["video_id"],
                language=row["language"],
                transcript_text=row["transcript_text"],
                summary_text=row["summary_text"],
                created_at=row["created_at"],
                updated_at=row["updated_at"]
            ))
        return transcriptions

    def update_transcription(self, transcription_id: int, **kwargs) -> bool:
        allowed_fields = ["transcript_text", "summary_text"]
        fields = {k: v for k, v in kwargs.items() if k in allowed_fields}

        if not fields:
            return False

        fields["updated_at"] = datetime.now().isoformat()

        set_clause = ", ".join([f"{k} = ?" for k in fields.keys()])
        values = list(fields.values()) + [transcription_id]

        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            f"UPDATE transcriptions SET {set_clause} WHERE id = ?",
            values
        )
        conn.commit()
        conn.close()

        logger.info(f"Транскрипция {transcription_id} обновлена")
        return True

    def add_download_log(self, log: DownloadLog) -> Optional[int]:
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO download_logs (video_id, action, log_text, status)
            VALUES (?, ?, ?, ?)
        """, (log.video_id, log.action, log.log_text, log.status))

        log_id = cursor.lastrowid
        conn.commit()
        conn.close()
        logger.info(f"Лог добавлен с ID: {log_id}")
        return log_id if log_id else 0

    def get_download_logs(self, video_id: int) -> List[DownloadLog]:
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            "SELECT * FROM download_logs WHERE video_id = ? ORDER BY created_at DESC",
            (video_id,)
        )

        rows = cursor.fetchall()
        conn.close()

        logs = []
        for row in rows:
            logs.append(DownloadLog(
                id=row["id"],
                video_id=row["video_id"],
                action=row["action"],
                log_text=row["log_text"],
                status=row["status"],
                created_at=row["created_at"]
            ))
        return logs

    def append_download_log(self, video_id: int, action: str, log_text: str, status: str = "pending") -> Optional[int]:
        log = DownloadLog(video_id=video_id, action=action, log_text=log_text, status=status)
        return self.add_download_log(log)


def init_database(db_path: str = "un_videos.db") -> Database:
    return Database(db_path)
