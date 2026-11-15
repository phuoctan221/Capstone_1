"""Enrich imported vocabulary with IPA, synonyms/antonyms and domain labels.

Chay tu thu muc backend/:

    .venv\\Scripts\\python.exe scripts/enrich_vocabularies.py --dry-run --sample 50
    .venv\\Scripts\\python.exe scripts/enrich_vocabularies.py --apply --fields phonetic --rpm 60
    .venv\\Scripts\\python.exe scripts/enrich_vocabularies.py --apply --fields topic,status
    .venv\\Scripts\\python.exe scripts/enrich_vocabularies.py --apply --fields all --no-backup

Only empty fields are filled; existing meanings, examples and translations are
never overwritten. The script is idempotent and resumable through the
``vocab_enrichment_jobs`` collection, and writes a JSON backup before applying.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv
from pymongo import MongoClient, UpdateOne

BACKEND_DIR = Path(__file__).resolve().parents[1]
SCRIPT_DIR = Path(__file__).resolve().parent
for _path in (BACKEND_DIR, SCRIPT_DIR):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))
load_dotenv(BACKEND_DIR / ".env")

for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        _stream.reconfigure(encoding="utf-8", errors="replace")

from import_english_vocab_pipeline import (  # noqa: E402
    RateLimiter,
    clean,
    fetch_dictionary,
    gemini_json,
    is_partial_ipa,
    normalize_word,
    now_utc,
)

MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "capstone1")
MONGO_URI = os.getenv("MONGO_URI")
DICTIONARY_RPM = max(1, int(os.getenv("DICTIONARY_RPM", "60")))
GEMINI_RPM = max(1, int(os.getenv("GEMINI_RPM", "10")))

VOCAB = "vocabularies"
JOBS = "vocab_enrichment_jobs"
FIELDS = ("phonetic", "topic", "status")
PROJECTION = {
    "word": 1,
    "word_key": 1,
    "phonetic": 1,
    "phonetic_source": 1,
    "part_of_speech": 1,
    "english_definition": 1,
    "example": 1,
    "synonyms": 1,
    "antonyms": 1,
    "topic": 1,
    "domain": 1,
    "topic_source": 1,
    "review_status": 1,
    "updated_at": 1,
}

TOKEN_RE = re.compile(r"[a-z][a-z'-]*")
TECH_HINTS = frozenset(
    {
        "algorithm", "api", "app", "application", "browser", "byte", "chip",
        "cloud", "code", "computer", "computing", "cyber", "data", "database",
        "device", "digital", "download", "email", "encryption", "file",
        "folder", "hardware", "internet", "keyboard", "laptop", "malware",
        "memory", "network", "online", "password", "pixel", "platform",
        "printer", "processor", "program", "programming", "robot", "screen",
        "security", "server", "software", "technology", "tech", "upload",
        "user", "virus", "web", "website",
    }
)
BUSINESS_HINTS = frozenset(
    {
        "account", "accounting", "advertising", "agreement", "audit", "bank",
        "bill", "brand", "budget", "business", "campaign", "client",
        "commerce", "company", "consumer", "contract", "corporate",
        "corporation", "cost", "credit", "customer", "deal", "debt",
        "department", "economy", "employee", "employer", "entrepreneur",
        "expense", "finance", "financial", "hire", "income", "insurance",
        "invest", "investment", "investor", "invoice", "loan", "management",
        "manager", "market", "marketing", "meeting", "merger", "money",
        "negotiate", "negotiation", "office", "partnership", "payment",
        "price", "product", "profit", "project", "receipt", "recruit",
        "revenue", "sale", "sales", "sell", "service", "shareholder", "startup",
        "stock", "strategy", "supply", "tax", "trade", "trading", "wage",
    }
)


def job_key(field: str, word_key: str) -> str:
    return f"{field}:{word_key}"


def parse_fields(value: str) -> list[str]:
    if value.strip().lower() == "all":
        return list(FIELDS)
    selected = []
    for item in value.split(","):
        field = item.strip().lower()
        if not field:
            continue
        if field not in FIELDS:
            raise ValueError(f"Unknown field {field!r}; choose from {', '.join(FIELDS)}")
        if field not in selected:
            selected.append(field)
    if not selected:
        raise ValueError("No fields selected")
    return selected


def parse_words(value: str) -> list[str]:
    words = []
    for item in value.split(","):
        key = normalize_word(item)
        if key and key not in words:
            words.append(key)
    return words


def missing_phonetic(value: object) -> bool:
    return is_partial_ipa(str(value or ""))


def normalize_ipa(value: object) -> str:
    text = clean(value)
    if not text or is_partial_ipa(text):
        return ""
    if text.startswith("[") and text.endswith("]"):
        text = text[1:-1]
    for separator in ("⁓", "~", " / "):
        if separator in text:
            text = text.split(separator)[0]
    text = text.strip()
    if text.startswith("/") and text.endswith("/"):
        inner = text[1:-1]
        if ", " in inner:
            inner = inner.split(", ")[0]
        return f"/{inner}/"
    if text.startswith("[") or text.endswith("]"):
        text = text.strip("[]")
    text = text.strip("/")
    if ", " in text:
        text = text.split(", ")[0]
    return f"/{text}/" if text else ""


def keyword_domain(word: str, definition: str = "") -> str:
    tokens = set(TOKEN_RE.findall(f"{word} {definition}".lower()))
    tech = len(tokens & TECH_HINTS)
    business = len(tokens & BUSINESS_HINTS)
    if tech > business:
        return "technology"
    if business > tech:
        return "business"
    return "general"


def parse_topic_response(payload: Any, words: list[str]) -> dict[str, set[str]]:
    allowed = {normalize_word(word) for word in words}
    buckets = {"technology": set(), "business": set()}
    if not isinstance(payload, dict):
        return buckets
    normalized = {str(key).strip().lower(): value for key, value in payload.items()}
    for domain in ("technology", "business"):
        values = normalized.get(domain)
        if isinstance(values, str):
            values = [values]
        if not isinstance(values, list):
            continue
        for value in values:
            key = normalize_word(value)
            if key in allowed:
                buckets[domain].add(key)
    return buckets


def dictionary_changes(doc: dict, candidate: dict) -> dict:
    changes: dict[str, Any] = {}
    phonetic = normalize_ipa(candidate.get("phonetic"))
    if missing_phonetic(doc.get("phonetic")) and phonetic:
        changes["phonetic"] = phonetic
        changes["phonetic_source"] = "dictionaryapi.dev"
    for field in ("english_definition", "example"):
        if not clean(doc.get(field)) and clean(candidate.get(field)):
            changes[field] = clean(candidate.get(field))
    for field in ("synonyms", "antonyms"):
        if not (doc.get(field) or []) and (candidate.get(field) or []):
            changes[field] = list(candidate[field])
    return changes


def mark_job(
    db: Any,
    field: str,
    word_key: str,
    status: str,
    *,
    enabled: bool,
    **extra: Any,
) -> None:
    if not enabled:
        return
    now = now_utc()
    db[JOBS].update_one(
        {"_id": job_key(field, word_key)},
        {
            "$set": {
                "field": field,
                "word_key": word_key,
                "status": status,
                "updated_at": now,
                **extra,
            },
            "$setOnInsert": {"created_at": now},
        },
        upsert=True,
    )


def write_backup(db: Any, path: Path) -> None:
    documents = list(db[VOCAB].find({}, PROJECTION))
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(documents, ensure_ascii=False, indent=2, default=str)
    path.write_text(payload, encoding="utf-8")
    print(f"Backup: {path} ({len(documents)} documents)")


def default_backup_path() -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return BACKEND_DIR / "data" / f"enrichment_backup_{stamp}.json"


def done_jobs(db: Any, field: str) -> set[str]:
    return {
        document["word_key"]
        for document in db[JOBS].find(
            {"field": field, "status": "done"}, {"word_key": 1}
        )
        if document.get("word_key")
    }


def enrich_phonetic(
    db: Any,
    http: httpx.Client,
    limiter: RateLimiter,
    args: argparse.Namespace,
    stats: dict[str, int],
) -> None:
    documents = list(db[VOCAB].find({}, PROJECTION))
    selected = set(parse_words(getattr(args, "words", "") or ""))
    if selected:
        documents = [
            document
            for document in documents
            if normalize_word(document.get("word_key") or document.get("word")) in selected
        ]
    done = set() if args.force else done_jobs(db, "phonetic")
    pending = [
        document
        for document in documents
        if normalize_word(document.get("word_key") or document.get("word")) not in done
        and (
            missing_phonetic(document.get("phonetic"))
            or not (document.get("synonyms") or [])
            or not (document.get("antonyms") or [])
            or not clean(document.get("english_definition"))
            or not clean(document.get("example"))
        )
    ]
    pending.sort(
        key=lambda document: (
            not missing_phonetic(document.get("phonetic")),
            not clean(document.get("english_definition")),
        )
    )
    limit = args.limit or args.sample
    if limit:
        pending = pending[:limit]

    print(f"\n[phonetic] pending={len(pending)} (rpm={args.rpm}, apply={args.apply})")
    for index, document in enumerate(pending, 1):
        word_key = normalize_word(document.get("word_key") or document.get("word"))
        word = document.get("word") or word_key
        try:
            candidate = fetch_dictionary(
                http, limiter, word, clean(document.get("part_of_speech"))
            )
        except (httpx.HTTPError, ValueError) as exc:
            stats["failed"] += 1
            mark_job(
                db,
                "phonetic",
                word_key,
                "failed",
                enabled=args.apply,
                last_error=f"{type(exc).__name__}: {str(exc)[:300]}",
            )
            print(f"  [{index}/{len(pending)}] {word}: failed ({type(exc).__name__})")
            continue

        changes = dictionary_changes(document, candidate)
        if changes:
            stats["updated"] += 1
            if args.apply:
                changes["updated_at"] = now_utc()
                db[VOCAB].update_one({"word_key": word_key}, {"$set": changes})
            print(
                f"  [{index}/{len(pending)}] {word}: "
                f"{', '.join(sorted(changes))} {changes.get('phonetic', '')}"
            )
        else:
            stats["unchanged"] += 1
            print(f"  [{index}/{len(pending)}] {word}: no new fields")
        mark_job(db, "phonetic", word_key, "done", enabled=args.apply)

    total = db[VOCAB].count_documents({})
    covered = total - db[VOCAB].count_documents(
        {"$or": [{"phonetic": {"$in": ["", None]}}, {"phonetic": {"$exists": False}}]}
    )
    stats["phonetic_covered"] = covered
    stats["vocabulary_total"] = total
    print(f"[phonetic] coverage: {covered}/{total}")


def topic_prompt(documents: list[dict]) -> str:
    lines = []
    for document in documents:
        definition = clean(document.get("english_definition")) or clean(
            document.get("meaning")
        )
        pos = clean(document.get("part_of_speech")) or "unknown"
        lines.append(f"- {document.get('word')} ({pos}): {definition[:180]}")
    return (
        "Classify these English vocabulary items for a learning app. "
        "Return ONLY a JSON object with two string arrays, \"technology\" and "
        "\"business\". Include a word only when its most common meaning clearly "
        "belongs to IT/technology or business/commerce/finance. Put every other "
        "word in neither array. Use the exact spelling from the input and do not "
        "include explanations.\n\n" + "\n".join(lines)
    )


def classify_batch(
    http: httpx.Client,
    limiter: RateLimiter,
    documents: list[dict],
    source: str,
) -> tuple[dict[str, str], str]:
    if source == "keyword":
        return (
            {
                normalize_word(document.get("word")): keyword_domain(
                    document.get("word", ""), document.get("english_definition", "")
                )
                for document in documents
            },
            "keyword",
        )
    try:
        payload = gemini_json(
            http,
            limiter,
            topic_prompt(documents),
            label=f"topics:{documents[0].get('word') if documents else '-'}",
        )
    except (httpx.HTTPError, ValueError, RuntimeError) as exc:
        print(
            f"  Gemini failed ({type(exc).__name__}: {str(exc)[:120]}), "
            "falling back to keyword heuristics"
        )
        return classify_batch(http, limiter, documents, "keyword")

    buckets = parse_topic_response(payload, [document.get("word", "") for document in documents])
    assignments = {}
    for document in documents:
        key = normalize_word(document.get("word"))
        if key in buckets["technology"]:
            assignments[key] = "technology"
        elif key in buckets["business"]:
            assignments[key] = "business"
        else:
            assignments[key] = "general"
    return assignments, "gemini"


def enrich_topics(
    db: Any,
    http: httpx.Client,
    limiter: RateLimiter,
    args: argparse.Namespace,
    stats: dict[str, int],
) -> None:
    selected = parse_words(getattr(args, "words", "") or "")
    if selected:
        query: dict[str, Any] = {"word_key": {"$in": selected}}
    else:
        query = {
            "$or": [
                {"domain": "general"},
                {"domain": None},
                {"domain": {"$exists": False}},
            ],
        }
    if not args.force:
        query["topic_source"] = {"$exists": False}
    documents = list(db[VOCAB].find(query, PROJECTION))
    limit = args.limit or args.sample
    if limit:
        documents = documents[:limit]

    batch_size = max(1, args.topic_batch_size)
    batches = [
        documents[index : index + batch_size]
        for index in range(0, len(documents), batch_size)
    ]
    print(
        f"\n[topic] pending={len(documents)} batches={len(batches)} "
        f"(source={args.topic_source}, apply={args.apply})"
    )

    for batch_index, batch in enumerate(batches, 1):
        assignments, source = classify_batch(http, limiter, batch, args.topic_source)
        now = now_utc()
        updates = []
        for document in batch:
            key = normalize_word(document.get("word_key") or document.get("word"))
            domain = assignments.get(normalize_word(document.get("word")), "general")
            updates.append(
                UpdateOne(
                    {"word_key": key},
                    {
                        "$set": {
                            "topic": domain,
                            "domain": domain,
                            "topic_source": source,
                            "updated_at": now,
                        }
                    },
                )
            )
            stats[f"topic_{domain}"] += 1
            mark_job(
                db,
                "topic",
                key,
                "done",
                enabled=args.apply,
                domain=domain,
                source=source,
            )
        if args.apply and updates:
            db[VOCAB].bulk_write(updates, ordered=False)
        print(
            f"  batch {batch_index}/{len(batches)}: "
            f"{sum(1 for value in assignments.values() if value == 'technology')} tech, "
            f"{sum(1 for value in assignments.values() if value == 'business')} business, "
            f"{sum(1 for value in assignments.values() if value == 'general')} general"
        )
        if not args.apply:
            for document in batch:
                key = normalize_word(document.get("word"))
                print(f"    {document.get('word')}: {assignments.get(key, 'general')}")


def normalize_metadata(db: Any, apply: bool, stats: dict[str, int]) -> None:
    query = {"$or": [{"review_status": None}, {"review_status": {"$exists": False}}]}
    count = db[VOCAB].count_documents(query)
    print(f"\n[status] null review_status={count} (apply={apply})")
    stats["status_null"] = count
    if apply and count:
        result = db[VOCAB].update_many(
            query, {"$set": {"review_status": "imported", "updated_at": now_utc()}}
        )
        stats["status_updated"] = result.modified_count
        print(f"  updated: {result.modified_count}")
    elif not apply and count:
        print("  dry-run: would set review_status=imported")

    mismatch_query = {
        "$expr": {"$ne": ["$topic", "$domain"]},
        "domain": {"$in": ["general", "technology", "business"]},
    }
    mismatches = list(db[VOCAB].find(mismatch_query, {"word_key": 1, "domain": 1}))
    print(f"\n[status] topic/domain mismatches={len(mismatches)} (apply={apply})")
    stats["topic_domain_mismatches"] = len(mismatches)
    if apply and mismatches:
        now = now_utc()
        updates = [
            UpdateOne(
                {"word_key": document["word_key"]},
                {"$set": {"topic": document["domain"], "updated_at": now}},
            )
            for document in mismatches
        ]
        result = db[VOCAB].bulk_write(updates, ordered=False)
        stats["topic_domain_fixed"] = result.modified_count
        print(f"  fixed: {result.modified_count}")
    elif not apply and mismatches:
        print("  dry-run: would align topic to domain")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Enrich vocabulary data in MongoDB")
    parser.add_argument(
        "--fields",
        default="all",
        help="all or comma-separated list: phonetic,topic,status",
    )
    parser.add_argument("--dry-run", action="store_true", help="call APIs but do not write")
    parser.add_argument("--apply", action="store_true", help="write changes to MongoDB")
    parser.add_argument("--limit", type=int, default=0, help="process at most N items per field")
    parser.add_argument("--sample", type=int, default=0, help="preview N items per field")
    parser.add_argument(
        "--words",
        default="",
        help="comma-separated word list; restrict enrichment to these words",
    )
    parser.add_argument("--rpm", type=int, default=DICTIONARY_RPM)
    parser.add_argument("--gemini-rpm", type=int, default=GEMINI_RPM)
    parser.add_argument("--topic-source", choices=("gemini", "keyword"), default="gemini")
    parser.add_argument("--topic-batch-size", type=int, default=50)
    parser.add_argument("--force", action="store_true", help="re-process finished jobs")
    parser.add_argument("--backup", type=Path, default=None, help="backup JSON path")
    parser.add_argument("--no-backup", action="store_true")
    parser.add_argument("--mongo-uri", default=None)
    parser.add_argument("--db-name", default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.apply and not args.dry_run:
        print("Dung --dry-run de xem truoc, hoac --apply de ghi vao DB")
        return 2
    if args.apply and args.dry_run:
        print("Chon mot trong --dry-run hoac --apply")
        return 2
    if args.sample and args.apply:
        print("--sample chi dung voi --dry-run")
        return 2

    uri = args.mongo_uri or MONGO_URI
    if not uri:
        print("Missing MONGO_URI in backend/.env")
        return 2
    db_name = args.db_name or MONGO_DB_NAME
    fields = parse_fields(args.fields)

    print(f"Database: {db_name}")
    print(f"Fields: {', '.join(fields)}")

    stats: dict[str, Any] = defaultdict(int)
    with MongoClient(uri, serverSelectionTimeoutMS=15000) as client:
        db = client[db_name]
        client.admin.command("ping")
        db[JOBS].create_index([("field", 1), ("status", 1)])
        db[JOBS].create_index([("word_key", 1)])

        if args.apply and not args.no_backup:
            write_backup(db, args.backup or default_backup_path())

        dictionary_limiter = RateLimiter(max(1, args.rpm))
        gemini_limiter = RateLimiter(max(1, args.gemini_rpm))
        with httpx.Client(timeout=httpx.Timeout(40.0, connect=10.0)) as http:
            if "phonetic" in fields:
                enrich_phonetic(db, http, dictionary_limiter, args, stats)
            if "topic" in fields:
                enrich_topics(db, http, gemini_limiter, args, stats)
        if "status" in fields:
            normalize_metadata(db, args.apply, stats)

    print("\nSummary:")
    for key in sorted(stats):
        print(f"  {key}: {stats[key]}")
    if not args.apply:
        print("Dry-run: khong ghi vao MongoDB.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
