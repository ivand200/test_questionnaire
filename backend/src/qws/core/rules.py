"""Pure rules: no I/O."""

import hashlib


def normalize_text(text: str) -> str:
    return " ".join(text.split()).casefold()


def question_hash(topic: str, text: str) -> str:
    return hashlib.sha256(f"{topic}|{normalize_text(text)}".encode()).hexdigest()
