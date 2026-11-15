"""Generate and import IT/Technology vocabulary into MongoDB using Gemini.

Unlike ``import_english_vocab_pipeline.py`` (which enriches a fixed CSV from a
dictionary API), this script asks Gemini to generate complete, deduplicated
vocabulary records in batches, then upserts them straight into the shared
``vocabularies`` collection. It is resumable: every run first reads the existing
``word_key`` values so re-running only adds genuinely new words.

Usage (from backend/)::

    .venv\\Scripts\\python.exe scripts\\generate_technology_vocab.py --dry-run --target 20
    .venv\\Scripts\\python.exe scripts\\generate_technology_vocab.py --target 1000

Notes:
    * The unique ``word_key`` index means a word already present in any domain
      (e.g. General English) is skipped, not re-tagged.
    * Records are marked ``review_status="auto_validated"`` because they are
      AI-generated rather than human-reviewed.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv
from pymongo import MongoClient

BASE_DIR = Path(__file__).resolve().parents[1]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))
load_dotenv(BASE_DIR / ".env")

MONGO_URI = os.getenv("MONGO_URI", "")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "capstone1")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
GEMINI_RPM = max(1, int(os.getenv("GEMINI_RPM", "10")))
COLLECTION = "vocabularies"
CEFR_LEVELS = {"A1", "A2", "B1", "B2", "C1", "C2"}
VALID_POS = {
    "noun", "verb", "adjective", "adverb", "preposition", "conjunction",
    "pronoun", "interjection", "abbreviation", "phrase",
}

SUBTOPICS = [
    "programming fundamentals",
    "software engineering",
    "web development",
    "mobile development",
    "databases and SQL",
    "networking",
    "cybersecurity",
    "cloud computing",
    "DevOps and CI/CD",
    "operating systems",
    "computer hardware",
    "data science and analytics",
    "artificial intelligence and machine learning",
    "algorithms and data structures",
    "software testing and QA",
    "UI/UX and product design",
    "embedded systems and electronics",
    "blockchain and cryptocurrencies",
    "game development",
    "IT support and troubleshooting",
    "version control and Git",
    "APIs and integration",
    "distributed systems",
    "virtualization and containers",
    "storage and file systems",
    "compilers and programming languages",
    "open source and licensing",
    "agile and IT project management",
    "computer graphics and multimedia",
    "natural language processing",
    "robotics and automation",
    "Internet of Things (IoT)",
    "quantum computing",
    "IT careers and workplace",
    "e-commerce and fintech technology",
    "email and collaboration tools",
    "spreadsheets and office software",
    "search engines and information retrieval",
    "accessibility and assistive technology",
    "green computing and sustainability",
]

LEVEL_BANDS = ["A1-A2", "B1", "B2", "C1", "C1-C2", "B1-B2"]


def normalize_word(value: Any) -> str:
    return " ".join(str(value or "").strip().casefold().split())


def normalize_meaning(value: Any) -> str:
    return " ".join(str(value or "").strip().casefold().split())


def clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def distinct(values: Any, limit: int = 5) -> list[str]:
    if not isinstance(values, list):
        return []
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        item = clean(value)
        if item and item.casefold() not in seen:
            seen.add(item.casefold())
            output.append(item)
    return output[:limit]


class RateLimiter:
    def __init__(self, rpm: int) -> None:
        self.interval = 60.0 / max(1, rpm)
        self.last_call = 0.0

    def wait(self) -> None:
        delta = time.monotonic() - self.last_call
        if delta < self.interval:
            time.sleep(self.interval - delta)
        self.last_call = time.monotonic()


def request_gemini(
    client: httpx.Client,
    limiter: RateLimiter,
    prompt: str,
    model: str,
) -> Any:
    if not GEMINI_API_KEY:
        raise SystemExit("Missing GEMINI_API_KEY in backend/.env")

    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent"
    )
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.7,
            "responseMimeType": "application/json",
            "maxOutputTokens": 8192,
        },
    }
    last_error: str = ""
    for attempt in range(4):
        limiter.wait()
        try:
            response = client.post(
                url, headers={"x-goog-api-key": GEMINI_API_KEY}, json=payload
            )
            if response.status_code in (408, 429, 500, 502, 503, 504) and attempt < 3:
                wait = (2**attempt) + random.uniform(0, 0.5)
                print(f"  Gemini {response.status_code}, retry in {wait:.1f}s")
                time.sleep(wait)
                continue
            response.raise_for_status()
            data = response.json()
            candidates = data.get("candidates") or []
            if not candidates:
                raise ValueError(
                    f"no candidate: {str(data.get('promptFeedback', ''))[:200]}"
                )
            parts = candidates[0].get("content", {}).get("parts", [])
            text = "".join(p.get("text", "") for p in parts if isinstance(p, dict))
            text = re.sub(
                r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.IGNORECASE
            )
            return json.loads(text)
        except (httpx.HTTPError, ValueError, json.JSONDecodeError) as exc:
            last_error = f"{type(exc).__name__}: {str(exc)[:200]}"
            if attempt == 3:
                break
            wait = (2**attempt) + random.uniform(0, 0.5)
            print(f"  Gemini error ({last_error}), retry in {wait:.1f}s")
            time.sleep(wait)
    raise RuntimeError(f"Gemini request failed: {last_error}")


def extract_items(result: Any) -> list[dict[str, Any]]:
    if isinstance(result, list):
        return [item for item in result if isinstance(item, dict)]
    if isinstance(result, dict):
        for value in result.values():
            if isinstance(value, list) and all(
                isinstance(item, dict) for item in value
            ):
                return value
    return []


def build_prompt(
    count: int,
    subtopic: str,
    level_band: str,
    avoid_words: list[str],
) -> str:
    avoid = ", ".join(avoid_words)
    return (
        "You are an English-Vietnamese dictionary generator for a vocabulary "
        "learning app. Generate exactly "
        f"{count} NEW English IT/Technology vocabulary items about "
        f'"{subtopic}" at CEFR level {level_band}.\n'
        "Return ONLY a valid JSON array. Each element must be an object with "
        "exactly these keys:\n"
        '{"word": English word or short term (1-3 words), '
        '"phonetic": IPA without slashes, '
        '"part_of_speech": one of noun/verb/adjective/adverb/phrase/abbreviation, '
        '"meaning": concise natural Vietnamese meaning, '
        '"english_definition": one concise English definition, '
        '"example": one natural English example sentence using the word, '
        '"synonyms": array of up to 5 English words, '
        '"antonyms": array of up to 5 English words (may be empty), '
        '"level": one of A1, A2, B1, B2, C1, C2}\n'
        "Rules: every word must be genuinely used in IT/software/technology; "
        "no proper nouns, product names, people, or programming language names; "
        "no duplicate words; Vietnamese meanings must be real translations, not "
        "the English definition. "
        + (
            f"Do NOT use any of these already-used words: {avoid}."
            if avoid
            else ""
        )
    )


def prepare_document(item: dict[str, Any], now: datetime) -> dict[str, Any] | None:
    word = clean(item.get("word"))
    word_key = normalize_word(word)
    meaning = clean(item.get("meaning"))
    definition = clean(item.get("english_definition"))
    pos = clean(item.get("part_of_speech")).lower()
    level = clean(item.get("level")).upper()

    if not word or not word_key or len(word) > 60:
        return None
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9 .+#/'-]{0,58}", word):
        return None
    if not meaning or not definition:
        return None
    if meaning.casefold() == definition.casefold():
        return None
    if pos not in VALID_POS:
        pos = "noun"
    if level not in CEFR_LEVELS:
        return None

    return {
        "word": word,
        "word_key": word_key,
        "meaning": meaning,
        "meaning_key": normalize_meaning(meaning),
        "phonetic": clean(item.get("phonetic")),
        "part_of_speech": pos,
        "english_definition": definition,
        "example": clean(item.get("example")),
        "synonyms": distinct(item.get("synonyms")),
        "antonyms": distinct(item.get("antonyms")),
        "topic": "technology",
        "domain": "technology",
        "level": level,
        "topic_source": "gemini",
        "cefr_source": "gemini_estimate",
        "data_source": "Gemini generated (IT/Technology)",
        "review_status": "auto_validated",
        "updated_at": now,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate IT/Technology vocabulary via Gemini and upsert to MongoDB"
    )
    parser.add_argument("--target", type=int, default=1000, help="new words to add")
    parser.add_argument("--batch-size", type=int, default=25, help="words per Gemini call")
    parser.add_argument("--max-batches", type=int, default=0, help="0 = unlimited")
    parser.add_argument("--rpm", type=int, default=GEMINI_RPM, help="Gemini requests/minute")
    parser.add_argument("--model", type=str, default=GEMINI_MODEL)
    parser.add_argument("--dry-run", action="store_true", help="preview only, no DB writes")
    args = parser.parse_args()

    if not MONGO_URI:
        raise SystemExit("Missing MONGO_URI in backend/.env")

    limiter = RateLimiter(args.rpm)
    created_total = 0
    skipped_total = 0

    with MongoClient(MONGO_URI, serverSelectionTimeoutMS=10000) as mongo:
        db = mongo[MONGO_DB_NAME]
        mongo.admin.command("ping")
        existing_keys = {
            doc["word_key"]
            for doc in db[COLLECTION].find({}, {"word_key": 1})
            if doc.get("word_key")
        }
        existing_words = [
            doc["word"]
            for doc in db[COLLECTION].find({}, {"word": 1})
            if doc.get("word")
        ]
        print(f"Existing vocabulary keys: {len(existing_keys)}")
        print(
            f"Target: {args.target} new IT words | batch={args.batch_size} "
            f"| rpm={args.rpm} | dry_run={args.dry_run}"
        )

        seen_new: set[str] = set()
        recent_words: list[str] = []
        batch_num = 0
        empty_batches = 0

        with httpx.Client(timeout=httpx.Timeout(120.0, connect=15.0)) as client:
            while created_total < args.target:
                if args.max_batches and batch_num >= args.max_batches:
                    break
                if empty_batches >= 8:
                    print("Stopping after 8 consecutive batches with no new words")
                    break
                batch_num += 1
                subtopic = random.choice(SUBTOPICS)
                level_band = random.choice(LEVEL_BANDS)
                need = min(args.batch_size, args.target - created_total)
                avoid_words = random.sample(
                    existing_words, min(250, len(existing_words))
                ) + recent_words[-150:]
                prompt = build_prompt(
                    max(need + 5, 10), subtopic, level_band, avoid_words
                )
                print(
                    f"\n[Batch {batch_num}] topic={subtopic!r} level={level_band} "
                    f"request={max(need + 5, 10)}"
                )
                try:
                    result = request_gemini(client, limiter, prompt, args.model)
                except RuntimeError as exc:
                    print(f"  Skipping batch: {exc}")
                    continue

                items = extract_items(result)
                print(f"  Gemini returned {len(items)} items")
                now = datetime.now(timezone.utc)
                batch_docs: list[dict[str, Any]] = []

                for item in items:
                    doc = prepare_document(item, now)
                    if doc is None:
                        skipped_total += 1
                        continue
                    key = doc["word_key"]
                    if key in existing_keys or key in seen_new:
                        skipped_total += 1
                        continue
                    seen_new.add(key)
                    recent_words.append(doc["word"])
                    batch_docs.append(doc)
                    if len(batch_docs) >= need:
                        break

                if not batch_docs:
                    empty_batches += 1
                    print("  No new valid words in this batch")
                    continue
                empty_batches = 0

                for doc in batch_docs[:5]:
                    print(
                        f"    + {doc['word']} ({doc['level']}, {doc['part_of_speech']}): "
                        f"{doc['meaning']}"
                    )

                if args.dry_run:
                    created_total += len(batch_docs)
                    for doc in batch_docs:
                        print(f"  [dry-run] {doc['word']} -> {doc['meaning']}")
                else:
                    from pymongo import UpdateOne

                    operations = [
                        UpdateOne(
                            {"word_key": doc["word_key"]},
                            {"$set": doc, "$setOnInsert": {"created_at": now}},
                            upsert=True,
                        )
                        for doc in batch_docs
                    ]
                    result_bulk = db[COLLECTION].bulk_write(operations, ordered=False)
                    created_total += result_bulk.upserted_count
                    existing_keys.update(doc["word_key"] for doc in batch_docs)
                    print(
                        f"  Inserted {result_bulk.upserted_count} "
                        f"(running total {created_total}/{args.target})"
                    )

        print("\n=== Done ===")
        print(f"Created: {created_total} | Skipped: {skipped_total}")
        if not args.dry_run:
            tech_count = db[COLLECTION].count_documents({"domain": "technology"})
            total = db[COLLECTION].count_documents({})
            print(f"Technology words now: {tech_count} (total {total})")


if __name__ == "__main__":
    main()
