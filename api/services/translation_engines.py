"""Локальные движки перевода фраз субтитров (en → ru)."""

import re
import threading
from typing import Callable

Progress = Callable[[str, int | None], None]

ENGINES = ("opus", "argos")
TARGETS = ("ru",)
_sentence_end = re.compile(r"(?<=[.!?])\s+")
_lock = threading.Lock()
_opus: tuple | None = None


def attach_translations(
    cues: list[dict],
    target: str,
    engine: str,
    progress: Progress,
) -> list[dict]:
    """Добавляет поле translation к каждой фразе, не меняя текст оригинала."""
    if not target:
        return cues
    texts = [cue["text"] for cue in cues]
    translations = translate_texts(texts, target, engine, progress)
    return [{**cue, "translation": text} for cue, text in zip(cues, translations)]


def translate_texts(
    texts: list[str],
    target: str,
    engine: str,
    progress: Progress,
) -> list[str]:
    """Переводит список фраз выбранным движком, предложение за предложением."""
    if target not in TARGETS:
        raise ValueError(f"Неподдерживаемый язык перевода: {target}")
    if engine not in ENGINES:
        raise ValueError(f"Неизвестный движок перевода: {engine}")
    sentences = [part for text in texts for part in split_sentences(text)]
    if not sentences:
        return ["" for _ in texts]
    progress(f"Перевожу {len(sentences)} предложений движком {engine}", None)
    translated = _translate_opus(sentences) if engine == "opus" else _translate_argos(sentences)
    return _rejoin(texts, translated)


def split_sentences(text: str) -> list[str]:
    """Делит фразу на предложения; пустые фрагменты отбрасываются."""
    return [part.strip() for part in _sentence_end.split(text.strip()) if part.strip()]


def _rejoin(texts: list[str], translated: list[str]) -> list[str]:
    """Собирает переводы предложений обратно в фразы исходного размера."""
    result = []
    position = 0
    for text in texts:
        count = len(split_sentences(text))
        result.append(" ".join(translated[position : position + count]))
        position += count
    return result


def _translate_opus(sentences: list[str]) -> list[str]:
    """Переводит через Marian opus-mt-en-ru с защитой от повторов."""
    import torch

    tokenizer, model = _load_opus()
    results = []
    with torch.no_grad():
        for index in range(0, len(sentences), 8):
            batch = sentences[index : index + 8]
            encoded = tokenizer(
                batch, return_tensors="pt", padding=True, truncation=True, max_length=256
            )
            generated = model.generate(
                **encoded, max_new_tokens=256, num_beams=1, no_repeat_ngram_size=3
            )
            results.extend(tokenizer.batch_decode(generated, skip_special_tokens=True))
    return results


def _load_opus() -> tuple:
    """Загружает модель opus один раз на процесс."""
    global _opus
    with _lock:
        if _opus is None:
            from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

            name = "Helsinki-NLP/opus-mt-en-ru"
            tokenizer = AutoTokenizer.from_pretrained(name)
            model = AutoModelForSeq2SeqLM.from_pretrained(name)
            model.eval()
            _opus = (tokenizer, model)
    return _opus


def _translate_argos(sentences: list[str]) -> list[str]:
    """Переводит через Argos Translate, устанавливая пакет en→ru при необходимости."""
    import argostranslate.package
    import argostranslate.translate

    _ensure_argos_package()
    translate = argostranslate.translate.translate
    return [translate(sentence, "en", "ru") for sentence in sentences]


def _ensure_argos_package() -> None:
    """Проверяет установку пакета en→ru и скачивает его при отсутствии."""
    import argostranslate.package

    installed = argostranslate.package.get_installed_packages()
    if any(pair.from_code == "en" and pair.to_code == "ru" for pair in installed):
        return
    argostranslate.package.update_package_index()
    packages = argostranslate.package.get_available_packages()
    package = next(p for p in packages if p.from_code == "en" and p.to_code == "ru")
    argostranslate.package.install_from_path(package.download())
