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

REQUEST_TIMEOUT = httpx.Timeout(60.0, connect=15.0)
MAX_ATTEMPTS = 4
RETRYABLE_STATUS = {429, 500, 502, 503, 504}
BATCH_CONCURRENCY = 4

_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


class AIServiceError(RuntimeError):
    """Lỗi khi gọi dịch vụ AI thất bại."""


class AIQuotaError(AIServiceError):
    """Hết hạn mức AI."""


def _is_quota_exhausted(body: str) -> bool:
    lowered = body.lower()
    return "exceeded your current quota" in lowered or "quota exceeded" in lowered


def _extract_json(text: str) -> dict:
    cleaned = _FENCE_RE.sub("", text.strip()).strip()
    # Tìm đoạn JSON {} nếu có text thừa xung quanh
    match = re.search(r"\{[\s\S]*\}", cleaned)
    candidate = match.group(0) if match else cleaned
    try:
        return json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise AIServiceError(
            f"AI trả về không phải JSON hợp lệ: {text[:200]}"
        ) from exc


def _extract_text(data: dict) -> str:
    candidates = data.get("candidates") or []
    if not candidates:
        block = data.get("promptFeedback", {}).get("blockReason", "khong ro")
        raise AIServiceError(f"Gemini không trả về candidate (blockReason={block})")
    parts = (candidates[0].get("content") or {}).get("parts") or []
    if not parts:
        raise AIServiceError("Gemini trả về candidate rỗng")
    return parts[0].get("text", "")


async def _call_gemini(prompt: str, label: str) -> str:
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
                            "Đã hết hạn mức Gemini. Hãy kiểm tra API Key."
                        )
                    raise AIServiceError(
                        f"Gemini HTTP {response.status_code}: {response.text[:200]}"
                    )
                if response.status_code != 200:
                    raise AIServiceError(
                        f"Gemini HTTP {response.status_code}: {response.text[:300]}"
                    )

                data = response.json()
                text = _extract_text(data)
                logger.info(
                    "AI (Gemini) trả về sau %.1fs (%s)", time.monotonic() - started, label
                )
                return text
            except (httpx.TimeoutException, httpx.TransportError) as exc:
                last_error = exc
                logger.warning(
                    "AI: lỗi mạng lần %s/%s cho %s: %s",
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

            if attempt < MAX_ATTEMPTS:
                await asyncio.sleep(2 * attempt)

    raise AIServiceError(
        f"Không gọi được Gemini sau {MAX_ATTEMPTS} lần: {last_error}"
    )


async def _call_cloudflare(prompt: str, label: str) -> str:
    """Gọi Cloudflare Workers AI khi có token cấu hình."""
    if not (settings.CF_ACCOUNT_ID and settings.CF_API_TOKEN):
        raise AIServiceError("Cloudflare AI is not configured")

    model = settings.CF_MODEL or "@cf/meta/llama-3.1-8b-instruct"
    url = f"https://api.cloudflare.com/client/v4/accounts/{settings.CF_ACCOUNT_ID}/ai/run/{model}"
    headers = {"Authorization": f"Bearer {settings.CF_API_TOKEN}"}
    payload = {
        "messages": [
            {
                "role": "system",
                "content": "You are a professional educational AI assistant. Always reply strictly with valid JSON only.",
            },
            {"role": "user", "content": prompt},
        ]
    }

    started = time.monotonic()
    async with httpx.AsyncClient(timeout=REQUEST_TIMEOUT) as client:
        response = await client.post(url, headers=headers, json=payload)
        if response.status_code != 200:
            raise AIServiceError(
                f"Cloudflare AI HTTP {response.status_code}: {response.text[:200]}"
            )
        data = response.json()
        result = data.get("result", {})
        text = result.get("response") or ""
        logger.info(
            "AI (Cloudflare) trả về sau %.1fs (%s)", time.monotonic() - started, label
        )
        return text


async def _call_ai(prompt: str, label: str) -> str:
    """Gọi AI linh hoạt: Ưu tiên Gemini, tự động fallback Cloudflare nếu có."""
    if settings.GEMINI_API_KEY:
        try:
            return await _call_gemini(prompt, label)
        except Exception as exc:
            logger.warning("Gemini call thất bại (%s), thử Cloudflare nếu có: %s", label, exc)
            if settings.CF_ACCOUNT_ID and settings.CF_API_TOKEN:
                return await _call_cloudflare(prompt, label)
            raise

    if settings.CF_ACCOUNT_ID and settings.CF_API_TOKEN:
        return await _call_cloudflare(prompt, label)

    raise AIServiceError("Chưa cấu hình GEMINI_API_KEY hoặc Cloudflare AI")


async def generate_vocabulary(word: str, target_language: str = "vi") -> dict:
    prompt = PROMPT_TEMPLATE.format(word=word)
    text = await _call_ai(prompt, label=word)
    return _extract_json(text)


async def suggest_words(topic: str, level: str, count: int) -> list[str]:
    prompt = SUGGEST_PROMPT_TEMPLATE.format(topic=topic, level=level, count=count)
    text = await _call_ai(prompt, label=f"suggest:{topic}/{level}")
    data = _extract_json(text)
    raw = data.get("words")
    if not isinstance(raw, list):
        raise AIServiceError("AI không trả về danh sách 'words'")
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
                    logger.error("AI batch: dừng do hết quota: %s", exc)
                return {
                    "word": word,
                    "ok": False,
                    "data": None,
                    "error": f"{type(exc).__name__}: {exc}"[:300],
                }

    return list(await asyncio.gather(*(one(word) for word in words)))

ERROR_ANALYSIS_PROMPT_TEMPLATE = """
You are an English learning assistant.

Analyze the learner's incorrect answer.

Question:
{question}

Correct answer:
{correct_answer}

Learner's answer:
{user_answer}

Vocabulary information:
- Word: {word}
- Meaning: {meaning}
- Part of speech: {part_of_speech}
- Level: {level}
- Example: {example}

Return ONLY valid JSON with EXACTLY this structure:
{{
  "error_type": "one of: Meaning, Grammar, Spelling, Word Form, Pronunciation, Vocabulary, Other",
  "what_went_wrong": "briefly explain what the learner did wrong",
  "explanation": "explain the reason in simple Vietnamese",
  "correct_answer": "{correct_answer}",
  "example": "give one simple English example",
  "tip": "give one short learning tip in Vietnamese"
}}

The explanation must be suitable for an English learner.
Do not blame or criticize the learner.
"""


async def generate_error_analysis(
    question: str,
    correct_answer: str,
    user_answer: str,
    vocabulary: dict,
) -> dict:
    prompt = ERROR_ANALYSIS_PROMPT_TEMPLATE.format(
        question=question,
        correct_answer=correct_answer,
        user_answer=user_answer,
        word=vocabulary.get("word", ""),
        meaning=vocabulary.get("meaning", ""),
        part_of_speech=vocabulary.get("part_of_speech", ""),
        level=vocabulary.get("level", "A1"),
        example=vocabulary.get("example", ""),
    )

    text = await _call_gemini(
        prompt,
        label=f"error-analysis:{vocabulary.get('word', '')}",
    )

    return _extract_json(text)