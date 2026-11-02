import asyncio
import json
import logging
import re
import time

import httpx

from app.core.config import settings

logger = logging.getLogger("uvicorn.error")

PROMPT_TEMPLATE = """
You are a professional English-Vietnamese dictionary assistant.
For the word "{word}", return a JSON object with EXACTLY this structure and nothing else:
{{
  "word": "{word}",
  "phonetic": "IPA pronunciation",
  "part_of_speech": "noun/verb/adjective/...",
  "meaning": "concise Vietnamese meaning",
  "example": "one natural English example sentence",
  "synonyms": ["syn1", "syn2", "syn3"],
  "antonyms": ["ant1", "ant2"],
  "topic": "one of: general, academic, business, technology, science, daily-life, travel",
  "level": "one of: A1, A2, B1, B2, C1, C2"
}}
Respond ONLY with valid JSON.
"""

SUGGEST_PROMPT_TEMPLATE = """
You are an English vocabulary curator for a learning app.
Suggest exactly {count} useful English words in the topic "{topic}" at CEFR level {level}.
Choose common, practical words a learner would actually need.
Respond ONLY with valid JSON in this exact shape:
{{"words": ["word1", "word2", "word3"]}}
"""

# Gemini free tier can be slow (cold start ~15-25s) and occasionally flaky.
REQUEST_TIMEOUT = httpx.Timeout(60.0, connect=15.0)
MAX_ATTEMPTS = 4
RETRYABLE_STATUS = {429, 500, 502, 503, 504}
BATCH_CONCURRENCY = 4

_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


class AIServiceError(RuntimeError):
    """Loi khi goi dich vu AI that bai."""


class AIQuotaError(AIServiceError):
    """Het hao nhan Gemini (quota ngay) - khong retry duoc, phai doi key/cho reset."""


def _is_quota_exhausted(body: str) -> bool:
    """Gemini bao het quota ngay bang thong diep nay (khac voi rate limit 1 phut)."""
    lowered = body.lower()
    return "exceeded your current quota" in lowered or "quota exceeded" in lowered


def _extract_json(text: str) -> dict:
    """Parse JSON, bo qua markdown fence neu Gemini boc them."""
    cleaned = _FENCE_RE.sub("", text.strip()).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise AIServiceError(
            f"Gemini tra ve khong phai JSON hop le: {text[:200]}"
        ) from exc


def _extract_text(data: dict) -> str:
    candidates = data.get("candidates") or []
    if not candidates:
        block = data.get("promptFeedback", {}).get("blockReason", "khong ro")
        raise AIServiceError(f"Gemini khong tra ve candidate (blockReason={block})")
    parts = (candidates[0].get("content") or {}).get("parts") or []
    if not parts:
        raise AIServiceError("Gemini tra ve candidate rong")
    return parts[0].get("text", "")


async def _call_gemini(prompt: str, label: str) -> str:
    """Goi Gemini (co retry) va tra ve raw text."""
    if not settings.GEMINI_API_KEY:
        raise AIServiceError("GEMINI_API_KEY is not configured")

    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{settings.GEMINI_MODEL}:generateContent"
    )
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.2, "response_mime_type": "application/json"},
    }

    started = time.monotonic()
    last_error: Exception | None = None

    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                response = await client.post(
                    url, params={"key": settings.GEMINI_API_KEY}, json=payload
                )

                if response.status_code in RETRYABLE_STATUS:
                    if _is_quota_exhausted(response.text):
                        raise AIQuotaError(
                            "Da het hao nhan Gemini (quota ngay). "
                            "Thu doi GEMINI_API_KEY hoac cho qua khoang reset."
                        )
                    raise AIServiceError(
                        f"Gemini tra ve HTTP {response.status_code}: {response.text[:200]}"
                    )
                if response.status_code != 200:
                    raise AIServiceError(
                        f"Gemini tra ve HTTP {response.status_code}: {response.text[:300]}"
                    )

                data = response.json()
                text = _extract_text(data)
                logger.info(
                    "AI: Gemini tra ve sau %.1fs (%s)", time.monotonic() - started, label
                )
                return text
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_error = exc
                logger.warning(
                    "AI: loi mang lan %s/%s cho %s: %s",
                    attempt,
                    MAX_ATTEMPTS,
                    label,
                    type(exc).__name__,
                )
            except AIQuotaError:
                raise
            except AIServiceError as exc:
                last_error = exc
                retryable = any(f"HTTP {code}" in str(exc) for code in RETRYABLE_STATUS)
                if not retryable:
                    raise
                logger.warning(
                    "AI: Gemini loi tam thoi lan %s/%s cho %s: %s",
                    attempt,
                    MAX_ATTEMPTS,
                    label,
                    str(exc)[:120],
                )

            if attempt < MAX_ATTEMPTS:
                await asyncio.sleep(2 * attempt)

    raise AIServiceError(
        f"Khong goi duoc Gemini sau {MAX_ATTEMPTS} lan: "
        f"{type(last_error).__name__}: {str(last_error)[:200]}"
    )


async def generate_vocabulary(word: str, target_language: str = "vi") -> dict:
    prompt = PROMPT_TEMPLATE.format(word=word)
    text = await _call_gemini(prompt, label=word)
    return _extract_json(text)


async def suggest_words(topic: str, level: str, count: int) -> list[str]:
    """AI goi y danh sach tu theo chu de + trinh do."""
    prompt = SUGGEST_PROMPT_TEMPLATE.format(topic=topic, level=level, count=count)
    text = await _call_gemini(prompt, label=f"suggest:{topic}/{level}")
    data = _extract_json(text)
    raw = data.get("words")
    if not isinstance(raw, list):
        raise AIServiceError("Gemini khong tra ve danh sach 'words'")
    words: list[str] = []
    seen: set[str] = set()
    for item in raw:
        word = str(item).strip()
        key = word.lower()
        if not word or key in seen:
            continue
        seen.add(key)
        words.append(word)
    return words[:count]


async def generate_vocabulary_batch(
    words: list[str], topic: str | None = None, level: str | None = None
) -> list[dict]:
    """Sinh chi tiet cho nhieu tu cung luc, khong de 1 tu len lam chan ca hang doi."""
    semaphore = asyncio.Semaphore(BATCH_CONCURRENCY)
    fatal: list[Exception] = []

    async def one(word: str) -> dict:
        async with semaphore:
            if fatal:
                return {
                    "word": word,
                    "ok": False,
                    "data": None,
                    "error": f"{type(fatal[0]).__name__}: {fatal[0]}"[:300],
                }
            try:
                data = await generate_vocabulary(word)
                if topic:
                    data["topic"] = topic
                if level:
                    data["level"] = level
                return {"word": word, "ok": True, "data": data, "error": None}
            except Exception as exc:
                if isinstance(exc, AIQuotaError) and not fatal:
                    fatal.append(exc)
                    logger.error("AI batch: dung ca loai do het hao nhan Gemini: %s", exc)
                else:
                    logger.warning("AI batch: that bai cho %r: %s", word, exc)
                return {
                    "word": word,
                    "ok": False,
                    "data": None,
                    "error": f"{type(exc).__name__}: {exc}"[:300],
                }

    return list(await asyncio.gather(*(one(word) for word in words)))
