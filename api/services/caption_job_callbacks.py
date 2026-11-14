"""Callbacks задачи подготовки субтитров: прогресс и частичные блоки."""

from api.services.caption_job_state import get_job, update_job
from api.services.caption_repository import CaptionRepository

TRANSCRIBING_TOKENS = ("WhisperX", "ASR", "Распознаю", "Перевожу", "перевожу")


def progress_callback(job_id: str):
    """Создаёт функцию обновления этапа и процента задачи."""
    def report(message: str, progress: int | None) -> None:
        """Обновляет текст и процент выполнения задачи."""
        update_job(
            job_id,
            status=_status_for(message, progress),
            message=message,
            progress=progress,
        )

    return report


def partial_callback(job_id: str):
    """Создаёт callback сохранения и публикации каждого готового блока."""
    def save_batch(batch_number: int, batch_cues: list[dict]) -> None:
        """Сохраняет накопленные cues и сразу публикует частичный результат."""
        job = get_job(job_id)
        if not job:
            return
        cues = job["cues"] + batch_cues
        CaptionRepository().save_cues(
            job["cache_key"],
            job["asset_key"],
            job["mode"],
            job["model"],
            job["language"],
            cues,
            is_complete=False,
        )
        update_job(
            job_id,
            status="partial",
            message=f"Готово блоков: {batch_number}; фраз: {len(cues)}",
            progress=None,
            cues=cues,
            blocks_done=batch_number,
        )

    return save_batch


def _status_for(message: str, progress: int | None) -> str:
    """Определяет этап задачи по тексту и проценту."""
    if progress is None and any(token in message for token in TRANSCRIBING_TOKENS):
        return "transcribing"
    if progress is not None and progress >= 65:
        return "archiving"
    return "downloading"
