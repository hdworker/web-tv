import logging
import os
from typing import Optional, Tuple

import requests

logger = logging.getLogger(__name__)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_URL = os.getenv("OPENAI_URL", "https://bothub.chat/api/v2/openai/v1")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")


class TextSummarizer:
    def __init__(self, api_key: Optional[str] = None, api_url: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or OPENAI_API_KEY
        self.api_url = api_url or OPENAI_URL
        self.model = model or OPENAI_MODEL

    def summarize(self, text: str, max_tokens: int = 2000) -> Tuple[bool, Optional[str]]:
        if not self.api_key:
            logger.error("API ключ не установлен")
            return False, None

        if not text or len(text.strip()) < 50:
            logger.warning("Текст слишком короткий для суммаризации")
            return False, None

        prompt = f"""Создай краткое резюме следующего текста на русском языке. 
Сохрани основные мысли и ключевые факты. Текст:

{text}

Резюме:"""

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": self.model,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "max_tokens": max_tokens,
            "temperature": 0.3
        }

        try:
            response = requests.post(
                f"{self.api_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=120
            )
            response.raise_for_status()
            
            result = response.json()
            summary = result["choices"][0]["message"]["content"].strip()
            
            return True, summary
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка при запросе к API: {e}")
            return False, None
        except (KeyError, IndexError) as e:
            logger.error(f"Ошибка при обработке ответа: {e}")
            return False, None

    def translate(self, text: str, target_lang: str = "ru") -> Tuple[bool, Optional[str]]:
        if not self.api_key:
            logger.error("API ключ не установлен")
            return False, None

        lang_names = {
            "ru": "русский",
            "en": "английский",
            "fr": "французский",
            "de": "немецкий",
            "es": "испанский"
        }
        
        target = lang_names.get(target_lang, target_lang)

        prompt = f"""Переведи следующий текст на {target}. Сохрани стиль и смысл оригинала.

Текст:
{text}

Перевод:"""

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": self.model,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "max_tokens": 4000,
            "temperature": 0.3
        }

        try:
            response = requests.post(
                f"{self.api_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=120
            )
            response.raise_for_status()
            
            result = response.json()
            translated = result["choices"][0]["message"]["content"].strip()
            
            return True, translated
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка при запросе к API: {e}")
            return False, None

    def extract_keywords(self, text: str, count: int = 10) -> Tuple[bool, Optional[str]]:
        if not self.api_key:
            logger.error("API ключ не установлен")
            return False, None

        prompt = f"""Извлеки {count} ключевых слов или фраз из текста. Верни только ключевые слова через запятую.

Текст:
{text}

Ключевые слова:"""

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": self.model,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "max_tokens": 500,
            "temperature": 0.3
        }

        try:
            response = requests.post(
                f"{self.api_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=60
            )
            response.raise_for_status()
            
            result = response.json()
            keywords = result["choices"][0]["message"]["content"].strip()
            
            return True, keywords
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Ошибка при запросе к API: {e}")
            return False, None


def summarize_text(text: str) -> Optional[str]:
    summarizer = TextSummarizer()
    success, summary = summarizer.summarize(text)
    return summary if success else None


def translate_text(text: str, target_lang: str = "ru") -> Optional[str]:
    summarizer = TextSummarizer()
    success, translated = summarizer.translate(text, target_lang)
    return translated if success else None
