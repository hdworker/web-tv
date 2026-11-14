# video_service.py — Сервис работы с видео
import os
from database import Database
from downloader import VideoDownloader


async def get_segments_info(video_id: int) -> dict:
    """Получить информацию о сегментах видео."""
    db = Database()
    video = db.get_video(video_id)
    if not video:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Видео не найдено")
    
    video_uuid = video.un_video_url.split("/")[-1]
    directory = os.path.join(".", "video", video_uuid)
    
    if not os.path.exists(directory):
        return {"last_segment": 0, "total_files": 0, "directory": directory}
    
    downloader = VideoDownloader()
    last_segment = downloader._get_last_valid_segment(directory)
    downloader.close()
    
    return _build_segments_response(directory, last_segment)


def _build_segments_response(directory: str, last_segment: int) -> dict:
    """Сборка ответа о сегментах."""
    ts_files = [f for f in os.listdir(directory) if f.endswith(".ts")]
    output_file = os.path.exists(os.path.join(directory, "output.ts"))
    return {
        "last_segment": last_segment,
        "total_files": len(ts_files),
        "has_output": output_file,
        "directory": directory
    }
