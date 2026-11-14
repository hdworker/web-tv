import logging
from datetime import datetime
from typing import List

from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel

from schedule_parser import get_schedule, get_schedule_period
from database import Database, Video

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/schedule", tags=["schedule"])


class ScheduleResponse(BaseModel):
    date: str
    items: List[dict]
    total: int


@router.get("/{date}", response_model=ScheduleResponse)
async def get_schedule_by_date(date: str):
    """
    Получить видео за конкретную дату (формат: YYYY-MM-DD).
    """
    logger.info(f"Запрос расписания на дату: {date}")

    try:
        datetime.strptime(date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="Неверный формат даты. Используйте YYYY-MM-DD")

    items = get_schedule(date)

    return ScheduleResponse(
        date=date,
        items=items,
        total=len(items)
    )


@router.get("/", response_model=ScheduleResponse)
async def get_schedule_by_period(
    start_date: str = Query(..., description="Начальная дата (YYYY-MM-DD)"),
    end_date: str = Query(..., description="Конечная дата (YYYY-MM-DD)")
):
    """
    Получить видео за период.
    """
    logger.info(f"Запрос расписания за период: {start_date} - {end_date}")

    try:
        datetime.strptime(start_date, "%Y-%m-%d")
        datetime.strptime(end_date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="Неверный формат даты. Используйте YYYY-MM-DD")

    items = get_schedule_period(start_date, end_date)

    return ScheduleResponse(
        date=f"{start_date} - {end_date}",
        items=items,
        total=len(items)
    )


@router.post("/save")
async def save_schedule_to_db(
    start_date: str = Query(...),
    end_date: str = Query(...)
):
    """
    Сохранить расписание в базу данных.
    """
    logger.info(f"Сохранение расписания в БД: {start_date} - {end_date}")

    items = get_schedule_period(start_date, end_date)
    logger.debug(f"Период распарсен, найдено {len(items)} групп")

    db = Database()
    saved_count = 0

    for group in items:
        for item in group.get("items", []):
            existing = db.get_videos(limit=1000)
            urls = [v.un_video_url for v in existing]

            if item["url"] not in urls:
                # Используем source_date как основную дату
                video_date = item.get("source_date", "") or item.get("schedule_time", "") or ""
                video = Video(
                    un_video_url=item["url"],
                    title=item["title"],
                    source_date=item.get("source_date", ""),
                    description=item.get("description", ""),
                    category=item.get("category", ""),
                    thumbnail=item.get("thumbnail", ""),
                    date=video_date,
                    duration=item.get("duration", ""),
                    status="new"
                )
                db.add_video(video)
                saved_count += 1
                logger.debug(f"Сохранено: {video.un_video_url} (date={video_date})")

    logger.info(f"Сохранено всего: {saved_count} видео")
    return {
        "message": f"Сохранено {saved_count} новых видео",
        "total_items": len(items),
        "saved": saved_count
    }