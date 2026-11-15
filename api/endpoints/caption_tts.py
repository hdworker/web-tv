"""Озвучка субтитров: голоса Edge TTS и синтез mp3."""

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from api.services.tts_edge import list_voices, synthesize

router = APIRouter(prefix="/captions/tts", tags=["captions"])

MAX_TEXT = 600


@router.get("/voices")
def voices(lang: str = "ru") -> dict:
    """Возвращает голоса Edge TTS для языка, например ru или en."""
    prefix = lang.strip().lower()
    if len(prefix) != 2:
        raise HTTPException(status_code=400, detail="Ожидается код языка из двух букв")
    try:
        items = list_voices(prefix)
    except Exception as error:  # Edge TTS ходит в сеть и может быть недоступен
        raise HTTPException(status_code=502, detail=f"Edge TTS недоступен: {error}") from error
    return {"engine": "edge", "lang": prefix, "voices": items}


@router.get("/audio")
def audio(
    text: str = Query(min_length=1, max_length=MAX_TEXT),
    voice: str = Query(min_length=3, max_length=64),
    rate: int = Query(default=0, ge=-50, le=50),
    pitch: int = Query(default=0, ge=-50, le=50),
    volume: int = Query(default=0, ge=-50, le=50),
) -> FileResponse:
    """Синтезирует фразу выбранным голосом Edge TTS и отдаёт mp3 из кеша."""
    if any(char not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ-"
               and not char.isdigit() for char in voice):
        raise HTTPException(status_code=400, detail="Некорректное имя голоса")
    try:
        path = synthesize(text, voice, rate=rate, pitch=pitch, volume=volume)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(status_code=502, detail=f"Edge TTS недоступен: {error}") from error
    return FileResponse(path, media_type="audio/mpeg", filename=f"{voice}.mp3")
