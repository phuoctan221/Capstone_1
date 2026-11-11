"""Exercise bank and server-side grading for Meaning, Spelling and Context.

Answers live only in MongoDB. The public question payload never contains
``correct_answer``/``accepted_answers``. Context items are real cloze items
generated from a validated example sentence; the learner's answer is compared
to the target word, not merely checked for appearing in the sentence.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone

from app.core.domains import normalize_domain
from app.db.mongodb import get_database

EXERCISES = "exercise_items"
SKILLS = ("meaning", "spelling", "context")
MIN_OPTIONS = 2

_PUNCT_EDGE = re.compile(r"^[\s\.,;:!?\"'()\[\]{}]+|[\s\.,;:!?\"'()\[\]{}]+$")


def normalize_text(value: str | None) -> str:
    return " ".join(str(value or "").strip().casefold().split())


def normalize_spelling(value: str | None) -> str:
    return _PUNCT_EDGE.sub("", normalize_text(value))


def _contains_word(sentence: str, word: str) -> bool:
    if not sentence or not word:
        return False
    pattern = r"(?<![A-Za-z])" + re.escape(word) + r"(?![A-Za-z])"
    return re.search(pattern, sentence, flags=re.IGNORECASE) is not None


def build_cloze(example: str, word: str) -> str | None:
    """Replace a whole-word occurrence of ``word`` with a blank."""
    if not _contains_word(example, word):
        return None
    pattern = re.compile(
        r"(?<![A-Za-z])" + re.escape(word) + r"(?![A-Za-z])", re.IGNORECASE
    )
    cloze, count = pattern.subn("____", example, count=1)
    if count != 1:
        return None
    return cloze.strip()


def _item_id(vocabulary_id: str, skill: str) -> str:
    return f"{vocabulary_id}:{skill}"


def _meaning_pool(words: list[dict]) -> list[str]:
    seen: set[str] = set()
    pool: list[str] = []
    for word in words:
        meaning = str(word.get("meaning") or "").strip()
        key = normalize_text(meaning)
        if meaning and key not in seen:
            seen.add(key)
            pool.append(meaning)
    return pool


def build_items_for_words(
    words: list[dict], domain: str | None = None, level: str | None = None
) -> list[dict]:
    """Pure function: build exercise documents (without DB access)."""
    pool = _meaning_pool(words)
    items: list[dict] = []
    for word in words:
        vocab_id = str(word.get("_id") or word.get("id"))
        meaning = str(word.get("meaning") or "").strip()
        english = str(word.get("word") or "").strip()
        item_domain = normalize_domain(domain or word.get("domain") or word.get("topic"))
        item_level = level or word.get("level") or "A1"
        common = {
            "vocabulary_id": vocab_id,
            "domain": item_domain,
            "level": item_level,
            "word": english,
            "meaning": meaning,
            "active": True,
        }

        # Meaning: multiple choice, backend stores the correct meaning.
        if english and meaning and len(pool) >= MIN_OPTIONS:
            options = [meaning]
            for candidate in pool:
                if normalize_text(candidate) == normalize_text(meaning):
                    continue
                if candidate not in options:
                    options.append(candidate)
                if len(options) >= 4:
                    break
            if len(options) >= MIN_OPTIONS:
                items.append(
                    {
                        **common,
                        "exercise_item_id": _item_id(vocab_id, "meaning"),
                        "skill": "meaning",
                        "prompt": f'Từ "{english}" có nghĩa là gì?',
                        "options": options,
                        "correct_answer": meaning,
                        "accepted_answers": [meaning],
                        "cloze": None,
                        "hint": english[:1] + "..." if english else None,
                    }
                )

        # Spelling: typed English word, prompt is the Vietnamese meaning.
        if english and meaning:
            items.append(
                {
                    **common,
                    "exercise_item_id": _item_id(vocab_id, "spelling"),
                    "skill": "spelling",
                    "prompt": f'Nhập từ tiếng Anh có nghĩa: "{meaning}"',
                    "options": [],
                    "correct_answer": english,
                    "accepted_answers": [english],
                    "cloze": None,
                    "hint": f"{len(english)} ký tự",
                }
            )

        # Context: cloze generated only from a validated example sentence.
        cloze = build_cloze(str(word.get("example") or ""), english)
        if english and cloze:
            items.append(
                {
                    **common,
                    "exercise_item_id": _item_id(vocab_id, "context"),
                    "skill": "context",
                    "prompt": "Điền từ tiếng Anh còn thiếu vào câu sau:",
                    "options": [],
                    "correct_answer": english,
                    "accepted_answers": [english],
                    "cloze": cloze,
                    "hint": meaning or None,
                }
            )
    return items


async def ensure_exercise_bank(
    words: list[dict], domain: str | None = None, level: str | None = None
) -> int:
    """Create/update exercise items for the given words. Idempotent."""
    db = get_database()
    items = build_items_for_words(words, domain=domain, level=level)
    if not items:
        return 0
    now = datetime.now(timezone.utc)
    from pymongo import UpdateOne

    operations = []
    for item in items:
        operations.append(
            UpdateOne(
                {"exercise_item_id": item["exercise_item_id"]},
                {
                    "$set": {**item, "updated_at": now},
                    "$setOnInsert": {"created_at": now},
                },
                upsert=True,
            )
        )
    await db[EXERCISES].bulk_write(operations, ordered=False)
    return len(operations)


async def get_items_for_ids(item_ids: list[str]) -> list[dict]:
    db = get_database()
    if not item_ids:
        return []
    found = {
        doc["exercise_item_id"]: doc
        async for doc in db[EXERCISES].find(
            {"exercise_item_id": {"$in": item_ids}}
        )
    }
    return [found[i] for i in item_ids if i in found]


def serialize_question(doc: dict) -> dict:
    return {
        "exercise_item_id": doc["exercise_item_id"],
        "vocabulary_id": doc["vocabulary_id"],
        "skill": doc["skill"],
        "prompt": doc.get("prompt", ""),
        "options": list(doc.get("options") or []),
        "cloze": doc.get("cloze"),
        "hint": doc.get("hint"),
        "level": doc.get("level", "A1"),
        "domain": doc.get("domain", "general"),
    }


def grade(doc: dict, answer: str) -> tuple[bool, str, str | None]:
    """Return (is_correct, correct_answer, error_type)."""
    skill = doc.get("skill")
    expected = str(doc.get("correct_answer") or "")
    accepted = [expected, *(doc.get("accepted_answers") or [])]
    if skill == "spelling":
        normalized = normalize_spelling(answer)
        correct = any(
            normalized and normalized == normalize_spelling(candidate)
            for candidate in accepted
        )
        error_type = None if correct else "spelling_error"
    elif skill == "context":
        normalized = normalize_spelling(answer)
        correct = any(
            normalized and normalized == normalize_spelling(candidate)
            for candidate in accepted
        )
        error_type = None if correct else "context_error"
    elif skill == "meaning":
        normalized = normalize_text(answer)
        correct = any(
            normalized and normalized == normalize_text(candidate)
            for candidate in accepted
        )
        error_type = None if correct else "meaning_error"
    else:
        raise ValueError("Invalid exercise skill")
    return correct, expected, error_type
