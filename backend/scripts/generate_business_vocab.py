"""Generate and import Business English vocabulary into MongoDB using Gemini.

Counterpart of ``generate_technology_vocab.py`` for the Business English domain.
It asks Gemini for complete, deduplicated records in batches and upserts them
straight into the shared ``vocabularies`` collection. Every run reads the
existing ``word_key`` values first, so re-running only adds genuinely new words.

Usage (from backend/)::

    .venv\\Scripts\\python.exe scripts\\generate_business_vocab.py --dry-run --target 20
    .venv\\Scripts\\python.exe scripts\\generate_business_vocab.py --target 3000

Notes:
    * The unique ``word_key`` index means a word already present in another
      domain (e.g. General English) is skipped, not re-tagged.
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

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

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
    "general business and commerce",
    "finance and accounting",
    "banking and investments",
    "marketing and branding",
    "digital marketing and social media",
    "sales and negotiation",
    "customer service and client relations",
    "human resources and recruitment",
    "leadership and management",
    "organizational structure",
    "business communication and email etiquette",
    "meetings and presentations",
    "project management",
    "operations and process management",
    "supply chain and logistics",
    "inventory and purchasing",
    "quality management",
    "strategy and competitive analysis",
    "business planning and entrepreneurship",
    "startups and venture capital",
    "economics and market trends",
    "international trade and export",
    "e-commerce and online retail",
    "business analytics and reporting",
    "budgeting and forecasting",
    "pricing and profitability",
    "contracts and business law",
    "corporate governance and compliance",
    "risk management and insurance",
    "taxation and audits",
    "corporate social responsibility and sustainability",
    "workplace culture and ethics",
    "productivity and time management",
    "business writing and documentation",
    "advertising and public relations",
    "research and consumer behavior",
    "mergers and acquisitions",
    "real estate and property business",
    "transportation and shipping",
    "business travel and networking",
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
        f"{count} NEW Business English vocabulary items about "
        f'"{subtopic}" at CEFR level {level_band}.\n'
        "Return ONLY a valid JSON array. Each element must be an object with "
        "exactly these keys:\n"
        '{"word": English word or short business term (1-3 words), '
        '"phonetic": IPA without slashes, '
        '"part_of_speech": one of noun/verb/adjective/adverb/phrase/abbreviation, '
        '"meaning": concise natural Vietnamese meaning, '
        '"english_definition": one concise English definition, '
        '"example": one natural English example sentence used in a business context, '
        '"synonyms": array of up to 5 English words, '
        '"antonyms": array of up to 5 English words (may be empty), '
        '"level": one of A1, A2, B1, B2, C1, C2}\n'
        "Rules: every word or phrase must be genuinely used in business, finance, "
        "marketing, management or the workplace; no proper nouns, company names, "
        "brand names or people; no duplicate words; Vietnamese meanings must be real "
        "translations, not the English definition. "
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
        "topic": "business",
        "domain": "business",
        "level": level,
        "topic_source": "gemini",
        "cefr_source": "gemini_estimate",
        "data_source": "Gemini generated (Business English)",
        "review_status": "auto_validated",
        "updated_at": now,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate Business English vocabulary via Gemini and upsert to MongoDB"
    )
    parser.add_argument("--target", type=int, default=3000, help="new words to add")
    parser.add_argument("--batch-size", type=int, default=25, help="words per Gemini call")
    parser.add_argument("--max-batches", type=int, default=0, help="0 = unlimited")
    parser.add_argument(
        "--max-empty-batches",
        type=int,
        default=12,
        help="stop after this many consecutive batches with no new words",
    )
    parser.add_argument("--rpm", type=int, default=GEMINI_RPM, help="Gemini requests/minute")
    parser.add_argument("--model", type=str, default=GEMINI_MODEL)
    parser.add_argument(
        "--models",
        type=str,
        default="",
        help="comma-separated model fallback list, rotated after each batch",
    )
    parser.add_argument("--dry-run", action="store_true", help="preview only, no DB writes")
    args = parser.parse_args()

    if not MONGO_URI:
        raise SystemExit("Missing MONGO_URI in backend/.env")

    models = [m.strip() for m in args.models.split(",") if m.strip()] or [args.model]
    model_index = 0
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
            f"Target: {args.target} new Business words | batch={args.batch_size} "
            f"| rpm={args.rpm} | dry_run={args.dry_run}"
        )

        seen_new: set[str] = set()
        recent_words: list[str] = []
        batch_num = 0
        empty_batches = 0

        with httpx.Client(timeout=httpx.Timeout(240.0, connect=15.0)) as client:
            while created_total < args.target:
                if args.max_batches and batch_num >= args.max_batches:
                    break
                if empty_batches >= args.max_empty_batches:
                    print(f"Stopping after {args.max_empty_batches} consecutive batches with no new words")
                    break
                batch_num += 1
                subtopic = random.choice(SUBTOPICS)
                level_band = random.choice(LEVEL_BANDS)
                need = min(args.batch_size, args.target - created_total)
                avoid_words = random.sample(
                    existing_words, min(100, len(existing_words))
                ) + recent_words[-150:]
                prompt = build_prompt(
                    max(need + 5, 10), subtopic, level_band, avoid_words
                )
                model = models[model_index % len(models)]
                print(
                    f"\n[Batch {batch_num}] topic={subtopic!r} level={level_band} "
                    f"request={max(need + 5, 10)} model={model}"
                )
                try:
                    result = request_gemini(client, limiter, prompt, model)
                except RuntimeError as exc:
                    if "429" in str(exc) and len(models) > 1:
                        model_index += 1
                        print("  Quota hit, switching model")
                    print(f"  Skipping batch: {exc}")
                    continue
                model_index += 1

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
            business_count = db[COLLECTION].count_documents({"domain": "business"})
            total = db[COLLECTION].count_documents({})
            print(f"Business words now: {business_count} (total {total})")


if __name__ == "__main__":
    main()
