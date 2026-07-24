import re

import nltk


_FALLBACK_BOUNDARY = re.compile(r"(?<=[.!?])\s+|\n+(?=\S)")


def split_sentences(text: str) -> list[str]:
    """Split text into non-empty sentences with an offline-safe fallback."""
    text = (text or "").strip()
    if not text:
        return []

    try:
        sentences = nltk.sent_tokenize(text)
    except LookupError:
        sentences = _FALLBACK_BOUNDARY.split(text)

    return [sentence.strip() for sentence in sentences if sentence.strip()]
