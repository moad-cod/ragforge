import re
import nltk


def split_sentences(text: str) -> list[str]:
    try:
        return nltk.sent_tokenize(text)
    except LookupError:
        return [s for s in re.split(r"(?<=[.!?])\s+", text) if s]
