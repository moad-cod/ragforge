import json
import logging
import re
from threading import Lock

from groq import Groq

from app.core.config import settings

logger = logging.getLogger(__name__)

_client = None
_client_lock = Lock()


def _get_client() -> Groq:
    global _client
    if _client is None:
        with _client_lock:
            if _client is None:
                if not settings.GROQ_API_KEY:
                    raise RuntimeError("GROQ_API_KEY is required for proposition chunking")
                _client = Groq(api_key=settings.GROQ_API_KEY)
    return _client

PROPOSITION_PROMPT = """Decompose the following text into simple, atomic propositions.
Each proposition must:
- Be a single self-contained fact
- Be understandable without context
- Be as short as possible

Return ONLY valid JSON in this exact shape:
{{"propositions": ["first proposition", "second proposition"]}}

Do not use markdown, code fences, comments, or explanations.

Example output:
{{"propositions": ["FloodScan data covers 1998 to 2022.", "WorldPop 2020 data was used.", "Somalia has two flood seasons."]}}

Text to decompose:
{text}"""


def _clean_json_text(raw: str) -> str:
    raw = raw.strip()
    raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.IGNORECASE)
    raw = re.sub(r"\s*```$", "", raw)
    raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL | re.IGNORECASE).strip()
    return raw

def _extract_json_candidate(raw: str) -> str:
    raw = _clean_json_text(raw)
    starts = [idx for idx in (raw.find("{"), raw.find("[")) if idx != -1]
    if not starts:
        raise ValueError("Model response did not contain JSON")

    start = min(starts)
    decoder = json.JSONDecoder()
    _, end = decoder.raw_decode(raw[start:])
    return raw[start:start + end]

def _parse_propositions(raw: str) -> list[str]:
    candidate = _extract_json_candidate(raw)
    data = json.loads(candidate)

    if isinstance(data, dict):
        data = data.get("propositions", data.get("items", []))

    if not isinstance(data, list):
        raise ValueError("Proposition response was not a list")

    propositions = [str(item).strip() for item in data if str(item).strip()]
    if not propositions:
        raise ValueError("Proposition response was empty")
    return propositions

def _status_code(exc: Exception) -> int | None:
    status = getattr(exc, "status_code", None)
    if status is None and getattr(exc, "response", None) is not None:
        status = getattr(exc.response, "status_code", None)
    try:
        return int(status) if status is not None else None
    except (TypeError, ValueError):
        return None

def _classify_failure(exc: Exception) -> str:
    status = _status_code(exc)
    message = str(exc).lower()
    if status == 429 or any(term in message for term in ("rate limit", "rate_limit", "quota", "too many requests")):
        return "Groq rate limit or quota reached"
    if status in {401, 403} or any(term in message for term in ("invalid api key", "unauthorized", "forbidden")):
        return "Groq authentication failed"
    if status and status >= 500:
        return "Groq service error"
    if isinstance(exc, json.JSONDecodeError) or "json" in message:
        return "Groq returned non-JSON content"
    return "Proposition extraction failed"

def chunk(text: str) -> list[str]:
    # Split into paragraphs first, then decompose each
    paragraphs = [p.strip() for p in text.split("\n\n") if len(p.strip()) > 50]
    all_propositions = []
    failures: dict[str, int] = {}
    first_failure_by_reason: dict[str, str] = {}

    for para in paragraphs:
        try:
            response = _get_client().chat.completions.create(
                model="qwen/qwen3.6-27b",
                messages=[{
                    "role": "user",
                    "content": PROPOSITION_PROMPT.format(text=para)
                }],
                max_tokens=1024,
                temperature=0,
            )
            raw = response.choices[0].message.content.strip()
            propositions = _parse_propositions(raw)
            all_propositions.extend(propositions)
        except Exception as e:
            # Fallback: keep the paragraph as-is
            reason = _classify_failure(e)
            failures[reason] = failures.get(reason, 0) + 1
            first_failure_by_reason.setdefault(reason, str(e))
            all_propositions.append(para)

    if failures:
        total_failures = sum(failures.values())
        for reason, count in failures.items():
            logger.warning(
                "%s; falling back to paragraph chunks for %s/%s paragraphs. First error: %s",
                reason,
                count,
                len(paragraphs),
                first_failure_by_reason[reason],
            )
        if total_failures == len(paragraphs) and "Groq rate limit or quota reached" in failures:
            logger.warning("All proposition requests hit Groq rate/quota limits. Consider skipping the proposition chunker until the quota resets.")

    return all_propositions
