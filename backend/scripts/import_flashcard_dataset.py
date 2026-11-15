"""Bulk-import a large English-Vietnamese vocabulary bank.

Sources:
  * Vocabulary data: dnizfor/vocabulary-flashcard-dataset (MIT), 3,357 entries
    with Vietnamese translations, CEFR level, part of speech and English
    definition. Based on the Oxford 3000/5000 word list.
  * Example sentences: Tatoeba English sentences (CC BY 2.0). The sentence id is
    stored in ``example_id`` for attribution.

Chay tu thu muc backend/:

    .venv\\Scripts\\python.exe scripts/import_flashcard_dataset.py --dry-run
    .venv\\Scripts\\python.exe scripts/import_flashcard_dataset.py --apply
    .venv\\Scripts\\python.exe scripts/import_flashcard_dataset.py --apply --limit 500

After a real import, rebuild lessons and the exercise bank:

    .venv\\Scripts\\python.exe scripts/seed_mvp.py --apply

The importer is idempotent. In the default ``merge`` mode it only inserts new
words and fills empty fields on existing words; it never overwrites an existing
meaning or example.
"""
from __future__ import annotations

import argparse
import bz2
import csv
import json
import os
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

from dotenv import load_dotenv
from pymongo import InsertOne, MongoClient, UpdateOne

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.domains import TOPIC_TO_DOMAIN, domain_for_topic  # noqa: E402

ALLOWED_TOPICS = set(TOPIC_TO_DOMAIN)

load_dotenv(BACKEND_DIR / ".env")

DATA_DIR = BACKEND_DIR / "data"
DEFAULT_SOURCE = DATA_DIR / "flashcard_vocab.json"
DEFAULT_SOURCE_URL = (
    "https://raw.githubusercontent.com/dnizfor/vocabulary-flashcard-dataset/"
    "main/data/data.json"
)
DEFAULT_EXAMPLES = DATA_DIR / "tatoeba_eng_sentences.tsv.bz2"
DEFAULT_EXAMPLES_URL = (
    "https://downloads.tatoeba.org/exports/per_language/eng/eng_sentences.tsv.bz2"
)
TOPIC_CSV = DATA_DIR / "vocabulary_input.csv"

CEFR_LEVELS = ("A1", "A2", "B1", "B2", "C1", "C2")
LEVEL_ORDER = {level: index for index, level in enumerate(CEFR_LEVELS)}
WORD_RE = re.compile(r"[A-Za-z][A-Za-z'-]*")
SPACE_RE = re.compile(r"\s+")
BLOCKED_TOKENS = {
    "fuck", "fucking", "shit", "bitch", "cunt", "dick", "pussy", "asshole",
    "bastard", "slut", "whore", "rape", "nigger", "nigga", "retard",
}


def clean(value: object) -> str:
    return SPACE_RE.sub(" ", str(value or "")).strip()


def normalize_word(value: object) -> str:
    return clean(value).lower()


def download(url: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_suffix(path.suffix + ".part")
    request = Request(url, headers={"User-Agent": "SmartVOCAB-importer/1.0"})
    print(f"Downloading {url}")
    with urlopen(request, timeout=120) as response, partial.open("wb") as handle:
        shutil.copyfileobj(response, handle)
    partial.replace(path)
    print(f"Saved {path} ({path.stat().st_size:,} bytes)")


def load_dataset(path: Path, url: str, refresh: bool) -> list[dict]:
    if refresh or not path.exists():
        download(url, path)
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise SystemExit("[LOI] Dataset phai la mot mang JSON")
    return [item for item in raw if isinstance(item, dict) and clean(item.get("word"))]


def load_topic_map() -> dict[str, str]:
    if not TOPIC_CSV.exists():
        return {}
    mapping: dict[str, str] = {}
    with TOPIC_CSV.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            word = normalize_word(row.get("word"))
            topic = clean(row.get("topic")).lower()
            if word and topic in ALLOWED_TOPICS:
                mapping[word] = topic
    return mapping


def vietnamese(entry: dict) -> str:
    for item in entry.get("translations") or []:
        if isinstance(item, dict) and item.get("language") == "vi":
            return clean(item.get("translation"))
    return ""


def dedupe(entries: list[dict]) -> tuple[list[dict], int]:
    """One document per word_key; keep the easiest CEFR entry and merge POS."""
    grouped: dict[str, dict] = {}
    duplicates = 0
    for entry in entries:
        key = normalize_word(entry.get("word"))
        meaning = vietnamese(entry)
        if not key or not meaning:
            continue
        level = clean(entry.get("level")).upper()
        if level not in LEVEL_ORDER:
            level = "A1"
        current = grouped.get(key)
        if current is None:
            grouped[key] = {**entry, "_vi": meaning, "_level": level}
            continue
        duplicates += 1
        current_level = current.get("_level", "A1")
        if LEVEL_ORDER[level] < LEVEL_ORDER.get(current_level, 99):
            current["_vi"] = meaning
            current["_level"] = level
            current["mean"] = entry.get("mean") or current.get("mean")
        pos = {clean(current.get("type")).lower(), clean(entry.get("type")).lower()}
        current["type"] = "/".join(sorted(value for value in pos if value))
    return list(grouped.values()), duplicates


def load_examples(
    path: Path, url: str, targets: set[str], refresh: bool
) -> dict[str, dict]:
    if not targets:
        return {}
    if refresh or not path.exists():
        download(url, path)

    single = {word for word in targets if " " not in word}
    multi = sorted((word for word in targets if " " in word), key=len, reverse=True)
    best: dict[str, tuple[int, str, str]] = {}

    with bz2.open(path, "rt", encoding="utf-8") as handle:
        for line in handle:
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 3:
                continue
            sentence_id, language, text = parts[0], parts[1], parts[2]
            if language != "eng":
                continue
            words = text.split()
            if not (4 <= len(words) <= 14):
                continue
            tokens = {token.strip("'-").lower() for token in WORD_RE.findall(text)}
            if tokens & BLOCKED_TOKENS:
                continue
            if "http" in text.lower() or "www." in text.lower() or "@" in text:
                continue
            matches = tokens & single
            if multi:
                lowered = text.lower()
                matches = set(matches)
                matches.update(word for word in multi if word in lowered)
            if not matches:
                continue

            score = 100 - abs(len(words) - 8) * 3
            if any(character.isdigit() for character in text):
                score -= 30
            if '"' in text:
                score -= 5
            if text.count(",") > 2:
                score -= 5
            if not text.endswith((".", "!", "?")):
                score -= 5

            for word in matches:
                previous = best.get(word)
                if previous is None or score > previous[0]:
                    best[word] = (score, text.strip(), sentence_id)

    return {
        word: {"text": text, "id": sentence_id}
        for word, (_, text, sentence_id) in best.items()
    }


def build_document(entry: dict, topic_map: dict[str, str], examples: dict[str, dict]) -> dict:
    word = clean(entry.get("word"))
    key = normalize_word(word)
    meaning = entry["_vi"]
    level = entry.get("_level") or "A1"
    topic = topic_map.get(key, "general")
    example = examples.get(key, {})
    sources = ["dnizfor/vocabulary-flashcard-dataset (MIT)"]
    if example:
        sources.append("Tatoeba (CC BY 2.0)")
    return {
        "word": word,
        "word_key": key,
        "phonetic": "",
        "part_of_speech": clean(entry.get("type")).lower(),
        "meaning": meaning,
        "meaning_key": meaning.casefold(),
        "example": example.get("text", ""),
        "example_id": example.get("id"),
        "example_source": "tatoeba" if example else None,
        "synonyms": [],
        "antonyms": [],
        "topic": topic,
        "domain": domain_for_topic(topic),
        "level": level,
        "english_definition": clean(entry.get("mean")),
        "cefr_source": "flashcard_dataset (Oxford 3000/5000 based)",
        "data_source": " + ".join(sources),
        "review_status": "imported",
        "source_word_id": entry.get("id"),
    }


FILL_FIELDS = (
    "phonetic",
    "part_of_speech",
    "example",
    "example_id",
    "example_source",
    "english_definition",
    "level",
    "topic",
    "domain",
    "meaning_key",
    "cefr_source",
)


def run(args: argparse.Namespace) -> None:
    if not args.dry_run and not args.apply:
        raise SystemExit("Dung --dry-run de xem truoc, hoac --apply de ghi vao DB")

    entries = load_dataset(Path(args.source), args.url, args.refresh)
    entries, duplicates = dedupe(entries)
    entries.sort(key=lambda item: (LEVEL_ORDER.get(item["_level"], 99), item["word"].lower()))
    if args.limit > 0:
        entries = entries[: args.limit]

    targets = {normalize_word(entry.get("word")) for entry in entries}
    examples = (
        {}
        if args.no_examples
        else load_examples(
            Path(args.examples_file), args.examples_url, targets, args.refresh
        )
    )
    topic_map = load_topic_map()

    documents = [build_document(entry, topic_map, examples) for entry in entries]
    documents = [doc for doc in documents if doc["word"] and doc["meaning"]]

    by_level: dict[str, int] = {}
    by_topic: dict[str, int] = {}
    for doc in documents:
        by_level[doc["level"]] = by_level.get(doc["level"], 0) + 1
        by_topic[doc["topic"]] = by_topic.get(doc["topic"], 0) + 1

    print(f"\nDataset entries: {len(entries) + duplicates}")
    print(f"Unique words: {len(documents)} (merged duplicates: {duplicates})")
    print(f"Examples found: {sum(1 for doc in documents if doc['example'])}")
    print(f"By level: {dict(sorted(by_level.items()))}")
    print(f"By topic: {dict(sorted(by_topic.items()))}")

    if args.dry_run and not args.apply:
        print("\nDry-run: khong ghi vao MongoDB.")
        for doc in documents[:5]:
            print(
                f"  {doc['word']} [{doc['level']}/{doc['topic']}] "
                f"{doc['meaning']} | {doc['example'][:70]}"
            )
        return

    uri = args.mongo_uri or os.environ.get("MONGO_URI")
    if not uri:
        raise SystemExit("Missing MONGO_URI in backend/.env")
    db_name = args.db_name or os.environ.get("MONGO_DB_NAME", "capstone1")
    client = MongoClient(uri)
    collection = client[db_name]["vocabularies"]

    keys = [doc["word_key"] for doc in documents]
    existing = {
        doc["word_key"]: doc
        for doc in collection.find({"word_key": {"$in": keys}}, {"word_key": 1, "meaning": 1,
            "phonetic": 1, "part_of_speech": 1, "example": 1, "english_definition": 1,
            "level": 1, "topic": 1, "domain": 1, "meaning_key": 1, "cefr_source": 1})
    }

    now = datetime.now(timezone.utc)
    inserts: list[InsertOne] = []
    updates: list[UpdateOne] = []
    created = filled = skipped = 0

    for doc in documents:
        current = existing.get(doc["word_key"])
        if current is None:
            payload = {**doc, "created_at": now, "updated_at": now}
            inserts.append(InsertOne(payload))
            created += 1
            continue

        changes: dict[str, object] = {}
        if args.mode == "overwrite":
            changes.update({key: doc[key] for key in FILL_FIELDS})
            changes["meaning"] = doc["meaning"]
            changes["data_source"] = doc["data_source"]
        else:
            for field in FILL_FIELDS:
                if not current.get(field) and doc.get(field):
                    changes[field] = doc[field]
            if not current.get("meaning") and doc.get("meaning"):
                changes["meaning"] = doc["meaning"]
                changes["meaning_key"] = doc["meaning_key"]
        if changes:
            changes["updated_at"] = now
            updates.append(UpdateOne({"word_key": doc["word_key"]}, {"$set": changes}))
            filled += 1
        else:
            skipped += 1

    if args.mode == "insert-only":
        updates = []
    if inserts or updates:
        collection.bulk_write(inserts + updates, ordered=False)

    print(f"\nApplied to {db_name}. Inserted: {created}, filled/updated: {len(updates)}, "
          f"unchanged: {skipped}")
    print("Next: .venv\\Scripts\\python.exe scripts/seed_mvp.py --apply")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Bulk import English-Vietnamese vocabulary")
    parser.add_argument("--source", default=str(DEFAULT_SOURCE), help="cached dataset JSON")
    parser.add_argument("--url", default=DEFAULT_SOURCE_URL, help="dataset download URL")
    parser.add_argument("--examples-file", default=str(DEFAULT_EXAMPLES))
    parser.add_argument("--examples-url", default=DEFAULT_EXAMPLES_URL)
    parser.add_argument("--no-examples", action="store_true", help="skip Tatoeba examples")
    parser.add_argument("--limit", type=int, default=0, help="only import the first N words")
    parser.add_argument("--mode", choices=("merge", "insert-only", "overwrite"), default="merge")
    parser.add_argument("--refresh", action="store_true", help="re-download source files")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--mongo-uri", default=None)
    parser.add_argument("--db-name", default=None)
    return parser.parse_args()


if __name__ == "__main__":
    run(parse_args())
