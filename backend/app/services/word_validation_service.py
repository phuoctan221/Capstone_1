"""Verify custom practice words against a dictionary, never generated definitions."""
import asyncio
import re
import time
from collections import OrderedDict
from difflib import SequenceMatcher
from urllib.parse import quote

import httpx
from fastapi import HTTPException

_verified = OrderedDict()
_WORD = re.compile(r"[a-z]+(?:['-][a-z]+)*")


def normalize_word(word: str) -> str:
    word = word.strip().lower().replace("’", "'")
    if len(word) > 80 or not _WORD.fullmatch(word):
        raise HTTPException(400, "Nhập một từ tiếng Anh mỗi lần, không kèm số hoặc ký tự đặc biệt.")
    return word


async def lookup(word: str, client: httpx.AsyncClient):
    cached = _verified.get(word)
    if cached and cached[0] > time.monotonic():
        _verified.move_to_end(word)
        return dict(cached[1])
    response = await client.get(f"https://api.dictionaryapi.dev/api/v2/entries/en/{quote(word, safe='')}")
    if response.status_code == 404:
        return None
    response.raise_for_status()
    entries = response.json()
    if not isinstance(entries, list):
        raise ValueError("Unexpected dictionary response")
    for entry in entries:
        if not isinstance(entry, dict) or str(entry.get("word", "")).lower() != word:
            continue
        for meaning in entry.get("meanings") or []:
            for definition in meaning.get("definitions") or []:
                if isinstance(definition.get("definition"), str) and definition["definition"].strip():
                    result = {"word": word, "definition": definition["definition"][:500]}
                    _verified[word] = (time.monotonic() + 86400, result)
                    if len(_verified) > 1000:
                        _verified.popitem(last=False)
                    return dict(result)
    return None


async def check_word(raw: str, suggest: bool = True):
    word = normalize_word(raw)
    try:
        async with httpx.AsyncClient(timeout=8) as client:
            entry = await lookup(word, client)
            if entry:
                return {**entry, "valid": True, "suggestions": []}
            suggestions = []
            if suggest:
                try:
                    response = await client.get("https://api.datamuse.com/words", params={"sp": word, "max": 8})
                    response.raise_for_status()
                    candidates = response.json()
                    if not isinstance(candidates, list):
                        candidates = []
                    names = list(dict.fromkeys(item.get("word", "").lower() for item in candidates if isinstance(item, dict) and isinstance(item.get("word"), str)))
                    names = [name for name in names if name != word and len(name) <= 80 and _WORD.fullmatch(name)
                             and SequenceMatcher(None, word, name).ratio() >= 0.65][:5]
                    results = await asyncio.gather(*(lookup(name, client) for name in names), return_exceptions=True)
                    suggestions = [result for result in results if isinstance(result, dict)]
                except (httpx.HTTPError, ValueError, TypeError):
                    pass  # Suggestions are optional; never accept an unverified spelling.
            return {"word": word, "valid": False, "suggestions": suggestions}
    except (httpx.HTTPError, ValueError, TypeError, AttributeError):
        raise HTTPException(503, "Chưa kiểm tra được từ lúc này. Bạn hãy thử lại nhé.") from None


async def validate_custom_words(words: list[str]):
    # Bound simultaneous requests when a client submits a whole exercise directly.
    semaphore = asyncio.Semaphore(4)
    async def validate(word):
        async with semaphore:
            return await check_word(word, suggest=False)
    results = await asyncio.gather(*(validate(word) for word in words))
    invalid = [result["word"] for result in results if not result["valid"]]
    if invalid:
        raise HTTPException(422, "Chưa xác nhận được từ: " + ", ".join(invalid) + ". Hãy kiểm tra lại trước khi luyện.")
