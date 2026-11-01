"""Resumable English vocabulary importer for a MongoDB-backed learning app.

Place in backend/scripts/import_english_vocab_pipeline.py and run from backend:
    python scripts/import_english_vocab_pipeline.py --limit 10
    python scripts/import_english_vocab_pipeline.py
    python scripts/import_english_vocab_pipeline.py --approve happy

The vocabulary_input.csv file is expected at backend/data/vocabulary_input.csv.
CEFR levels must be checked by a human against an appropriate reference.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import random
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote

import httpx
from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.errors import OperationFailure


BASE_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BASE_DIR / ".env")

MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "capstone1")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite")
DICTIONARY_RPM = max(1, int(os.getenv("DICTIONARY_RPM", "30")))
GEMINI_RPM = max(1, int(os.getenv("GEMINI_RPM", "10")))

DEFAULT_CSV = BASE_DIR / "data" / "vocabulary_input.csv"
CEFR_LEVELS = {"A1", "A2", "B1", "B2", "C1", "C2"}
ALLOWED_TOPICS = {
    "general", "daily-life", "travel", "business",
    "technology", "science", "academic",
}
RAW_CACHE_COLLECTION = "vocab_raw_cache"


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def normalize_word(value: str) -> str:
    return clean(value).lower()


def distinct(values: list[Any], limit: int = 5) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        if not isinstance(value, str):
            continue
        item = clean(value)
        if item and item.casefold() not in seen:
            seen.add(item.casefold())
            output.append(item)
    return output[:limit]


def ensure_indexes(db: Any) -> None:
    """Backfill `word_key` roi tao unique index (idempotent, an toan khi chay lai)."""
    collection = db["vocabularies"]

    missing = collection.find(
        {"$or": [{"word_key": {"$exists": False}}, {"word_key": None}]},
        {"word": 1},
    )
    for doc in missing:
        key = normalize_word(doc.get("word", ""))
        if key:
            collection.update_one({"_id": doc["_id"]}, {"$set": {"word_key": key}})

    duplicates = list(
        collection.aggregate(
            [
                {"$group": {"_id": "$word_key", "count": {"$sum": 1}, "words": {"$push": "$word"}}},
                {"$match": {"count": {"$gt": 1}, "_id": {"$nin": [None, ""]}}},
            ]
        )
    )
    if duplicates:
        report = "\n".join(
            f"  {item['_id']!r}: {item['count']} ban ghi ({item['words']})"
            for item in duplicates[:20]
        )
        raise RuntimeError(
            "Khong the tao unique index vi co tu trung (word_key):\n"
            f"{report}\nHay xoa/gop cac ban ghi trung roi chay lai."
        )

    try:
        collection.create_index("word_key", unique=True, name="word_key_unique")
    except OperationFailure as exc:
        raise RuntimeError(f"Tao unique index word_key that bai: {exc}") from exc

    db["vocab_import_jobs"].create_index("status", name="status_idx")
    db[RAW_CACHE_COLLECTION].create_index(
        "updated_at", expireAfterSeconds=60 * 60 * 24 * 30, name="cache_ttl"
    )


def cache_get(db: Any, word: str) -> dict[str, Any] | None:
    doc = db[RAW_CACHE_COLLECTION].find_one({"_id": word})
    payload = (doc or {}).get("payload")
    if not isinstance(payload, dict):
        return None
    if not isinstance(payload.get("dictionary"), dict):
        return None
    if not clean(payload.get("meaning")):
        return None
    return payload


def cache_put(db: Any, word: str, payload: dict[str, Any]) -> None:
    db[RAW_CACHE_COLLECTION].update_one(
        {"_id": word},
        {"$set": {"payload": payload, "updated_at": now_utc()}},
        upsert=True,
    )


class RateLimiter:
    """Simple single-process limiter; configured in requests per minute."""

    def __init__(self, rpm: int):
        self.interval = 60.0 / rpm
        self.last_call = 0.0

    def wait(self) -> None:
        delta = time.monotonic() - self.last_call
        if delta < self.interval:
            time.sleep(self.interval - delta)
        self.last_call = time.monotonic()


def request_json(
    client: httpx.Client,
    limiter: RateLimiter,
    method: str,
    url: str,
    **kwargs: Any,
) -> Any:
    """Retry only transient HTTP and transport errors, with backoff + jitter."""
    last_error: Exception | None = None
    for attempt in range(4):
        limiter.wait()
        try:
            response = client.request(method, url, **kwargs)
            # Non-retryable errors (400, 401, 403, 404...) fail immediately.
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as exc:
            last_error = exc
            status = exc.response.status_code
            if status not in (408, 429, 500, 502, 503, 504) or attempt == 3:
                raise
            retry_after = exc.response.headers.get("Retry-After", "")
            try:
                wait_seconds = max(0.0, float(retry_after))
            except ValueError:
                wait_seconds = (2**attempt) + random.uniform(0, 0.5)
        except httpx.RequestError as exc:
            last_error = exc
            if attempt == 3:
                raise
            wait_seconds = (2**attempt) + random.uniform(0, 0.5)
        else:
            # This is never reached: either return or an exception is raised.
            raise RuntimeError("Unexpected request result")
        print(f"  Retrying in {wait_seconds:.1f}s (attempt {attempt + 1}/4)")
        time.sleep(wait_seconds)

    raise RuntimeError(f"Request failed: {last_error}")


def is_partial_ipa(value: str) -> bool:
    value = clean(value)
    return not value or value.startswith(("/-", "-")) or value.endswith(("-/", "-"))


def best_phonetic(entry: dict[str, Any]) -> str:
    options = [entry.get("phonetic", "")]
    options.extend(p.get("text", "") for p in entry.get("phonetics", []) if isinstance(p, dict))
    candidates = distinct(options, 30)
    candidates = [x for x in candidates if not is_partial_ipa(x)]
    if not candidates:
        return ""
    return max(candidates, key=lambda x: ("ˈ" in x, len(x)))


def extract_dictionary_entry(entries: Any, preferred_pos: str) -> dict[str, Any]:
    """Choose a definition for the requested POS, preferring a supplied example.

    This is a heuristic, not a guarantee of the most common word sense.
    """
    if not isinstance(entries, list):
        raise ValueError("Dictionary API response is not a list")

    candidates: list[tuple[tuple[int, int, int], dict[str, Any], dict[str, Any], dict[str, Any]]] = []
    for entry_num, entry in enumerate(entries):
        if not isinstance(entry, dict):
            continue
        for meaning in entry.get("meanings", []):
            if not isinstance(meaning, dict):
                continue
            pos = clean(meaning.get("partOfSpeech")).lower()
            for definition in meaning.get("definitions", []):
                if not isinstance(definition, dict) or not clean(definition.get("definition")):
                    continue
                score = (
                    int(bool(preferred_pos) and pos == preferred_pos),
                    int(bool(definition.get("example"))),
                    -entry_num,
                )
                candidates.append((score, entry, meaning, definition))

    if not candidates:
        raise ValueError("No usable dictionary definition")

    _, entry, meaning, definition = max(candidates, key=lambda item: item[0])
    synonyms = list(meaning.get("synonyms") or []) + list(definition.get("synonyms") or [])
    antonyms = list(meaning.get("antonyms") or []) + list(definition.get("antonyms") or [])

    return {
        "word": normalize_word(entry.get("word", "")),
        "phonetic": best_phonetic(entry),
        "part_of_speech": clean(meaning.get("partOfSpeech")).lower(),
        "english_definition": clean(definition.get("definition")),
        "example": clean(definition.get("example")),
        "synonyms": distinct(synonyms),
        "antonyms": distinct(antonyms),
    }


def fetch_dictionary(
    client: httpx.Client,
    limiter: RateLimiter,
    word: str,
    preferred_pos: str,
) -> dict[str, Any]:
    url = "https://api.dictionaryapi.dev/api/v2/entries/en/" + quote(word, safe="")
    data = request_json(client, limiter, "GET", url)
    result = extract_dictionary_entry(data, preferred_pos)
    # Store the original requested spelling so keys are consistent.
    result["word"] = word
    return result


def gemini_json(
    client: httpx.Client,
    limiter: RateLimiter,
    prompt: str,
    label: str,
) -> dict[str, Any]:
    """Goi Gemini va parse JSON (bo qua markdown fence neu co)."""
    if not GEMINI_API_KEY:
        raise ValueError("Missing GEMINI_API_KEY in .env")

    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.2,
            "responseMimeType": "application/json",
        },
    }
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{GEMINI_MODEL}:generateContent"
    )
    data = request_json(
        client,
        limiter,
        "POST",
        url,
        headers={"x-goog-api-key": GEMINI_API_KEY},
        json=payload,
    )
    candidates = data.get("candidates") or []
    if not candidates:
        raise ValueError(
            f"Gemini khong tra ve candidate cho {label}: "
            f"{str(data.get('promptFeedback', ''))[:180]}"
        )
    parts = candidates[0].get("content", {}).get("parts", [])
    text = "".join(part.get("text", "") for part in parts if isinstance(part, dict))
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip(), flags=re.IGNORECASE).strip()
    try:
        result = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Gemini tra ve JSON khong hop le cho {label}: {cleaned[:120]}") from exc
    if not isinstance(result, dict):
        raise ValueError(f"Gemini JSON khong phai object cho {label}")
    return result


def translate_gemini(
    client: httpx.Client,
    limiter: RateLimiter,
    word: str,
    pos: str,
    english_definition: str,
) -> dict[str, str]:
    """Dich nghia sang tieng Viet va uoc luong CEFR neu CSV khong co."""
    prompt = (
        "Translate the following dictionary sense to concise, natural Vietnamese "
        "for English learners. Respect its part of speech and exact intended meaning. "
        "Do not invent a different sense. Also estimate the CEFR level of the word. "
        "Return only a JSON object with two string properties: "
        '"meaning_vi" and "level" (one of A1, A2, B1, B2, C1, C2).\n'
        f"Word: {word}\nPart of speech: {pos}\nDefinition: {english_definition}"
    )
    result = gemini_json(client, limiter, prompt, label=f"translate:{word}")
    translation = clean(result.get("meaning_vi"))
    if not translation:
        raise ValueError("Gemini returned an empty Vietnamese meaning")
    level = clean(result.get("level")).upper()
    return {
        "meaning": translation,
        "level": level if level in CEFR_LEVELS else "",
    }


def gemini_generate_full(
    client: httpx.Client,
    limiter: RateLimiter,
    word: str,
    topic: str,
    level: str,
) -> dict[str, Any]:
    """Fallback khi dictionary API loi: Gemini sinh day du 9 muc cua mot tu."""
    allowed_topics = ", ".join(sorted(ALLOWED_TOPICS))
    prompt = (
        "You are an English-Vietnamese dictionary for a learning app. "
        f"For the word \"{word}\", return one JSON object with exactly these keys:\n"
        '{"word": string, "phonetic": IPA string, "part_of_speech": string, '
        '"english_definition": concise English definition, "meaning": concise Vietnamese meaning, '
        '"example": one natural English example sentence, '
        '"synonyms": [up to 5 English words], "antonyms": [up to 5 English words], '
        f'"topic": one of {allowed_topics}, "level": one of A1, A2, B1, B2, C1, C2}}\n'
        f"Preferred topic: {topic}. Preferred CEFR level: {level or 'estimate it'}.\n"
        "Respond ONLY with valid JSON."
    )
    result = gemini_json(client, limiter, prompt, label=f"full:{word}")

    meaning = clean(result.get("meaning"))
    if not meaning:
        raise ValueError("Gemini khong tra ve meaning")

    result_level = clean(result.get("level")).upper()
    return {
        "word": word,
        "phonetic": clean(result.get("phonetic")),
        "part_of_speech": clean(result.get("part_of_speech")).lower(),
        "english_definition": clean(result.get("english_definition")),
        "meaning": meaning,
        "example": clean(result.get("example")),
        "synonyms": distinct(result.get("synonyms") or []),
        "antonyms": distinct(result.get("antonyms") or []),
        "topic": clean(result.get("topic")).lower(),
        "level": result_level if result_level in CEFR_LEVELS else "",
    }


def merge_gemini_fallback(
    dictionary: dict[str, Any],
    fallback: dict[str, Any],
) -> dict[str, Any]:
    """Giu du lieu dictionary tot nhat, chi lap cac muc con thieu bang Gemini."""
    merged = {**dictionary}
    for key in ("phonetic", "part_of_speech", "english_definition", "example"):
        if not clean(merged.get(key)):
            merged[key] = fallback.get(key, "")
    for key in ("synonyms", "antonyms"):
        if not merged.get(key):
            merged[key] = fallback.get(key, [])
    return merged


def validate_candidate(candidate: dict[str, Any], requested_pos: str) -> list[str]:
    problems = []
    if not candidate.get("word"):
        problems.append("missing_word")
    if not candidate.get("english_definition"):
        problems.append("missing_english_definition")
    if not candidate.get("meaning") or clean(candidate.get("meaning")).casefold() == clean(
        candidate.get("english_definition")
    ).casefold():
        problems.append("missing_or_untranslated_meaning")
    if not candidate.get("part_of_speech"):
        problems.append("missing_part_of_speech")
    if not requested_pos:
        problems.append("part_of_speech_not_verified")
    elif candidate.get("part_of_speech") != requested_pos:
        problems.append("part_of_speech_mismatch")
    if is_partial_ipa(candidate.get("phonetic", "")):
        problems.append("missing_or_partial_ipa")
    if not candidate.get("example"):
        problems.append("missing_example")
    if candidate.get("topic") not in ALLOWED_TOPICS:
        problems.append("invalid_topic")
    if candidate.get("level") not in CEFR_LEVELS:
        problems.append("invalid_cefr_level")
    return problems


def publish_candidate(db: Any, candidate: dict[str, Any], *, human_reviewed: bool = False) -> None:
    now = now_utc()
    word = clean(candidate.get("word")) or normalize_word(candidate.get("word", ""))
    document = {
        key: candidate.get(key)
        for key in (
            "word", "phonetic", "part_of_speech", "meaning", "example",
            "synonyms", "antonyms", "topic", "level", "english_definition", "cefr_source"
        )
    }
    document["word"] = word
    document["word_key"] = normalize_word(word)
    document["updated_at"] = now
    document["review_status"] = "human_approved" if human_reviewed else "auto_validated"
    document["data_source"] = candidate.get("data_source") or (
        "dictionaryapi.dev + Gemini; CEFR from CSV/Gemini estimate"
    )
    db["vocabularies"].update_one(
        {"word_key": document["word_key"]},
        {"$set": document, "$setOnInsert": {"created_at": now}},
        upsert=True,
    )


def load_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        required = {"word", "topic", "part_of_speech", "level", "cefr_source"}
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"Missing CSV columns: {', '.join(sorted(missing))}")
        records = []
        seen = set()
        for line_number, row in enumerate(reader, start=2):
            word = normalize_word(row.get("word", ""))
            if not word or word in seen:
                continue
            topic = clean(row.get("topic")).lower() or "general"
            level = clean(row.get("level")).upper()
            if topic not in ALLOWED_TOPICS:
                raise ValueError(
                    f"CSV line {line_number}: invalid topic {topic!r}; "
                    f"allowed: {', '.join(sorted(ALLOWED_TOPICS))}"
                )
            if level and level not in CEFR_LEVELS:
                raise ValueError(
                    f"CSV line {line_number}: invalid CEFR level {level!r}"
                )
            seen.add(word)
            records.append({
                "word": word,
                "topic": topic,
                "part_of_speech": clean(row.get("part_of_speech")).lower(),
                "level": level,
                "cefr_source": clean(row.get("cefr_source")),
            })
        return records


def dictionary_from_fallback(fallback: dict[str, Any]) -> dict[str, Any]:
    return {
        "word": fallback["word"],
        "phonetic": fallback["phonetic"],
        "part_of_speech": fallback["part_of_speech"],
        "english_definition": fallback["english_definition"],
        "example": fallback["example"],
        "synonyms": fallback["synonyms"],
        "antonyms": fallback["antonyms"],
    }


def dictionary_is_complete(dictionary: dict[str, Any]) -> bool:
    """Dictionary API thieu field cot loi -> can Gemini bo sung."""
    core = ("phonetic", "part_of_speech", "english_definition", "example")
    if any(not clean(dictionary.get(key)) for key in core):
        return False
    return not is_partial_ipa(dictionary.get("phonetic", ""))


def run_import(
    db: Any,
    input_csv: Path,
    limit: int,
    force: bool,
    retry_failed: bool = False,
) -> None:
    records = load_csv(input_csv)
    if limit > 0:
        records = records[:limit]
    jobs = db["vocab_import_jobs"]
    dictionary_limiter = RateLimiter(DICTIONARY_RPM)
    gemini_limiter = RateLimiter(GEMINI_RPM)
    summary = {"published": 0, "needs_review": 0, "failed": 0, "skipped": 0}

    with httpx.Client(timeout=httpx.Timeout(40.0, connect=10.0)) as http:
        for index, row in enumerate(records, 1):
            word = row["word"]
            previous = jobs.find_one({"_id": word}, {"status": 1})
            previous_status = (previous or {}).get("status")

            if retry_failed and previous_status != "failed":
                summary["skipped"] += 1
                print(f"[{index}/{len(records)}] {word}: not failed ({previous_status or 'none'}) (skip)")
                continue
            if (
                not retry_failed
                and not force
                and previous_status in {"published", "needs_review"}
            ):
                summary["skipped"] += 1
                print(f"[{index}/{len(records)}] {word}: already {previous_status} (skip)")
                continue

            print(f"[{index}/{len(records)}] {word}: fetching")
            jobs.update_one(
                {"_id": word},
                {"$set": {
                    "status": "fetching", "requested_pos": row["part_of_speech"],
                    "updated_at": now_utc(), "last_error": None,
                }, "$inc": {"attempts": 1}},
                upsert=True,
            )
            try:
                cached = None if force else cache_get(db, word)
                if cached:
                    dictionary = cached["dictionary"]
                    meaning_vi = cached["meaning"]
                    gemini_level = clean(cached.get("level")).upper()
                    data_source = cached.get("data_source", "cache")
                    print("  Cache hit, skip dictionary/Gemini calls")
                else:
                    data_source = "dictionaryapi.dev + Gemini"
                    try:
                        dictionary = fetch_dictionary(
                            http, dictionary_limiter, word, row["part_of_speech"]
                        )
                    except (httpx.HTTPError, ValueError) as exc:
                        print(
                            f"  Dictionary API loi ({type(exc).__name__}: {str(exc)[:120]}), "
                            "chuyen sang Gemini"
                        )
                        fallback = gemini_generate_full(
                            http, gemini_limiter, word, row["topic"], row["level"]
                        )
                        dictionary = dictionary_from_fallback(fallback)
                        meaning_vi = fallback["meaning"]
                        gemini_level = fallback["level"]
                        data_source = "Gemini full (dictionary API failed)"
                    else:
                        jobs.update_one({"_id": word}, {"$set": {
                            "status": "translating", "updated_at": now_utc(),
                            "candidate": dictionary,
                        }})

                        if not dictionary_is_complete(dictionary):
                            print("  Dictionary thieu field, dung Gemini bo sung")
                            fallback = gemini_generate_full(
                                http, gemini_limiter, word, row["topic"], row["level"]
                            )
                            dictionary = merge_gemini_fallback(dictionary, fallback)
                            meaning_vi = fallback["meaning"]
                            gemini_level = fallback["level"]
                            data_source = "dictionaryapi.dev + Gemini fill"
                        else:
                            try:
                                translated = translate_gemini(
                                    http, gemini_limiter, word,
                                    dictionary["part_of_speech"],
                                    dictionary["english_definition"],
                                )
                                meaning_vi = translated["meaning"]
                                gemini_level = translated["level"]
                            except (httpx.HTTPError, ValueError) as exc:
                                print(
                                    f"  Dich Gemini loi ({type(exc).__name__}: {str(exc)[:120]}), "
                                    "dung Gemini full"
                                )
                                fallback = gemini_generate_full(
                                    http, gemini_limiter, word, row["topic"], row["level"]
                                )
                                dictionary = merge_gemini_fallback(dictionary, fallback)
                                meaning_vi = fallback["meaning"]
                                gemini_level = fallback["level"]
                                data_source = "dictionaryapi.dev + Gemini full fallback"

                    cache_put(db, word, {
                        "dictionary": dictionary,
                        "meaning": meaning_vi,
                        "level": gemini_level,
                        "data_source": data_source,
                    })

                level = row["level"] or gemini_level
                candidate = {
                    **dictionary,
                    "word": word,
                    "meaning": meaning_vi,
                    "topic": row["topic"],
                    "level": level,
                    "cefr_source": row["cefr_source"] or (
                        "csv" if row["level"] else ("gemini_estimate" if level else "")
                    ),
                    "data_source": data_source,
                }
                issues = validate_candidate(candidate, row["part_of_speech"])
                if issues:
                    status = "needs_review"
                    print(f"  Needs review: {', '.join(issues)}")
                else:
                    publish_candidate(db, candidate)
                    status = "published"
                    print(f"  Published ({candidate['level']}, {data_source})")
                jobs.update_one({"_id": word}, {"$set": {
                    "status": status, "candidate": candidate, "issues": issues,
                    "data_source": data_source,
                    "updated_at": now_utc(), "last_error": None,
                }})
                summary[status] += 1
            except (httpx.HTTPError, ValueError, RuntimeError) as exc:
                message = f"{type(exc).__name__}: {str(exc)[:350]}"
                jobs.update_one({"_id": word}, {"$set": {
                    "status": "failed", "last_error": message, "updated_at": now_utc(),
                }})
                summary["failed"] += 1
                print(f"  Failed: {message}")

    print("\nImport summary:", json.dumps(summary, ensure_ascii=False))
    print("Review pending records in MongoDB collection: vocab_import_jobs")


def approve_word(db: Any, word: str) -> None:
    word = normalize_word(word)
    jobs = db["vocab_import_jobs"]
    job = jobs.find_one({"_id": word})
    if not job:
        raise ValueError(f"No import job for {word!r}")
    if job.get("status") != "needs_review":
        raise ValueError("Only needs_review jobs can be approved with this command")
    candidate = job.get("candidate")
    if not isinstance(candidate, dict):
        raise ValueError("Job has no candidate data")
    issues = validate_candidate(candidate, clean(job.get("requested_pos")).lower())
    if issues:
        raise ValueError("Still requires corrections: " + ", ".join(issues))
    # Human is responsible for verifying the sense, CEFR and Vietnamese translation.
    publish_candidate(db, candidate, human_reviewed=True)
    jobs.update_one({"_id": word}, {"$set": {
        "status": "published", "issues": [], "approved_at": now_utc(),
        "updated_at": now_utc(), "last_error": None,
    }})
    print(f"Approved and published: {word}")


def export_json(db: Any, path: Path) -> None:
    # Export every usable record so seed JSON is UTF-8 clean and complete.
    query = {
        "word": {"$type": "string", "$ne": ""},
        "meaning": {"$type": "string", "$ne": ""},
    }
    fields = {"_id": 0, "created_at": 0, "updated_at": 0, "word_key": 0}
    documents = list(db["vocabularies"].find(query, fields))
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        json.dump(documents, f, ensure_ascii=False, indent=2)
    print(f"Exported {len(documents)} records to {path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Reliable vocabulary import pipeline")
    parser.add_argument("--input", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--limit", type=int, default=0, help="0 means all CSV words")
    parser.add_argument("--force", action="store_true", help="Re-import reviewed/published words")
    parser.add_argument(
        "--retry-failed",
        action="store_true",
        help="Chi chay lai cac tu co job status = failed",
    )
    parser.add_argument("--approve", type=str, help="Publish one manually corrected staging record")
    parser.add_argument("--export-json", action="store_true", help="Export JSON after import or approval")
    parser.add_argument("--only-export", action="store_true", help="Export JSON without calling any APIs")
    args = parser.parse_args()

    if not MONGO_URI:
        parser.error("Missing MONGO_URI in backend/.env")

    with MongoClient(MONGO_URI, serverSelectionTimeoutMS=10000) as mongo:
        db = mongo[MONGO_DB_NAME]
        mongo.admin.command("ping")
        ensure_indexes(db)
        if args.only_export:
            export_json(db, BASE_DIR / "data" / "vocabulary_seed.json")
        else:
            if args.approve:
                approve_word(db, args.approve)
            else:
                run_import(
                    db,
                    args.input,
                    args.limit,
                    args.force,
                    retry_failed=args.retry_failed,
                )
            if args.export_json:
                export_json(db, BASE_DIR / "data" / "vocabulary_seed.json")


if __name__ == "__main__":
    main()
