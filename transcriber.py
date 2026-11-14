import logging
import os
import subprocess
import json
from pathlib import Path
from typing import Optional, Tuple, List, Dict

logger = logging.getLogger(__name__)


class VideoTranscriber:
    def __init__(self):
        self.model = None

    def extract_audio(self, video_path: str, output_path: Optional[str] = None) -> Optional[str]:
        if not os.path.exists(video_path):
            logger.error(f"Видео файл не найден: {video_path}")
            return None

        if output_path is None:
            video_name = Path(video_path).stem
            output_path = f"audio_{video_name}.wav"

        command = [
            "ffmpeg",
            "-i", video_path,
            "-vn",
            "-acodec", "pcm_s16le",
            "-ar", "16000",
            "-ac", "1",
            "-y",
            output_path
        ]

        try:
            logger.info(f"Извлечение аудио из: {video_path}")
            subprocess.run(command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            logger.info(f"Аудио сохранено: {output_path}")
            return output_path
        except subprocess.CalledProcessError as e:
            logger.error(f"Ошибка при извлечении аудио: {e}")
            return None

    def transcribe(self, video_path: str, language: Optional[str] = None, audio_path: Optional[str] = None) -> Tuple[bool, Optional[Dict]]:
        try:
            import whisperx
        except ImportError:
            logger.error(" whisperx не установлен. Установите: pip install whisperx")
            return False, None

        if audio_path is None:
            audio_path = self.extract_audio(video_path)
            if audio_path is None:
                return False, None

        try:
            logger.info("Загрузка модели WhisperX...")
            self.model = whisperx.load_model("large-v3", device="cpu")
            
            logger.info("Распознавание речи...")
            result = self.model.transcribe(audio_path, language=language)
            
            logger.info("Выравнивание текста...")
            model_a, metadata = whisperx.load_align_model(language_code=result["language"])
            result = whisperx.align(result["segments"], model_a, metadata, audio_path, device="cpu")
            
            segments = []
            for segment in result.get("segments", []):
                segments.append({
                    "start": segment.get("start", 0),
                    "end": segment.get("end", 0),
                    "text": segment.get("text", "").strip()
                })
            
            full_text = " ".join([s["text"] for s in segments])
            
            result_data = {
                "text": full_text,
                "segments": segments,
                "language": result.get("language", "unknown")
            }

            if audio_path and audio_path.startswith("audio_"):
                try:
                    os.remove(audio_path)
                    logger.info(f"Временный аудио файл удален: {audio_path}")
                except:
                    pass

            return True, result_data

        except Exception as e:
            logger.error(f"Ошибка при транскрипции: {e}")
            return False, None

    def transcribe_with_diarization(self, video_path: str, language: Optional[str] = None) -> Tuple[bool, Optional[Dict]]:
        try:
            import whisperx
        except ImportError:
            logger.error("whisperx не установлен")
            return False, None

        audio_path = self.extract_audio(video_path)
        if audio_path is None:
            return False, None

        try:
            logger.info("Загрузка модели WhisperX...")
            model = whisperx.load_model("large-v3", device="cpu")
            
            logger.info("Распознавание речи с диаризацией...")
            result = model.transcribe(audio_path, language=language)
            
            logger.info("Диаризация...")
            diarize_model = whisperx.DiarizationPipeline(use_auth_token=None)
            diarize_segments = diarize_model(audio_path)
            
            result = whisperx.assign_word_speakers(diarize_segments, result)
            
            full_text = " ".join([s["text"].strip() for s in result["segments"] if s.get("text")])
            
            result_data = {
                "text": full_text,
                "segments": result.get("segments", []),
                "language": result.get("language", "unknown")
            }

            if audio_path and audio_path.startswith("audio_"):
                try:
                    os.remove(audio_path)
                except:
                    pass

            return True, result_data

        except Exception as e:
            logger.error(f"Ошибка при транскрипции с диаризацией: {e}")
            return False, None


def transcribe_video(video_path: str, language: Optional[str] = None) -> Optional[Dict]:
    transcriber = VideoTranscriber()
    success, result = transcriber.transcribe(video_path, language)
    return result if success else None
