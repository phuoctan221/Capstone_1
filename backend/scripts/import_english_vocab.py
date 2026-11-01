import os
import json
import re
from pathlib import Path
from typing import List, Dict, Any, Optional
import httpx
from pymongo import MongoClient
from dotenv import load_dotenv

# -----------------------------
# Load env
# -----------------------------
BASE_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BASE_DIR / ".env")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "capstone1")

# -----------------------------
# Config
# -----------------------------
ENGLISH_API = "https://api.dictionaryapi.dev/api/v2/entries/en/{word}"
GEMINI_MODEL = "gemini-1.5-flash"
OUTPUT_JSON_PATH = BASE_DIR / "data" / "vocabulary_seed.json"

# -----------------------------
# Helpers
# -----------------------------
def normalize_word(word: str) -> str:
    return re.sub(r"\s+", " ", word.strip()).lower()

def safe_get(obj: Dict[str, Any], *keys, default=None):
    cur = obj
    for key in keys:
        if not isinstance(cur, dict) or key not in cur:
            return default
        cur = cur[key]
    return cur

def clean_text(value: str) -> str:
    if value is None:
        return ""
    return re.sub(r"\s+", " ", value).strip()

def get_first_example(meanings: List[Dict[str, Any]]) -> str:
    for meaning in meanings:
        for defn in meaning.get("definitions", []):
            ex = defn.get("example")
            if ex:
                return clean_text(ex)
    return ""

def get_first_definition(meanings: List[Dict[str, Any]]) -> str:
    for meaning in meanings:
        for defn in meaning.get("definitions", []):
            text = defn.get("definition")
            if text:
                return clean_text(text)
    return ""

def get_synonyms_antonyms(meanings: List[Dict[str, Any]]) -> tuple[List[str], List[str]]:
    synonyms = []
    antonyms = []

    for meaning in meanings:
        for item in meaning.get("definitions", []):
            for key, arr in [("synonyms", synonyms), ("antonyms", antonyms)]:
                values = item.get(key, [])
                for v in values:
                    if isinstance(v, str):
                        arr.append(clean_text(v))

    seen_s = set()
    seen_a = set()
    synonyms = [s for s in synonyms if not (s.lower() in seen_s or seen_s.add(s.lower()))]
    antonyms = [a for a in antonyms if not (a.lower() in seen_a or seen_a.add(a.lower()))]

    return synonyms[:5], antonyms[:5]

def get_part_of_speech(meanings: List[Dict[str, Any]]) -> str:
    for meaning in meanings:
        pos = meaning.get("partOfSpeech", "")
        if pos:
            return clean_text(pos)
    return ""

def translate_with_gemini(text: str) -> Optional[str]:
    if not GEMINI_API_KEY:
        return None

    prompt = (
        f"Bạn hãy dịch câu/định nghĩa sau sang tiếng Việt một cách tự nhiên, ngắn gọn và chính xác. "
        f"Chỉ trả về kết quả tiếng Việt, không giải thích thêm.\n\nText: {text}"
    )

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
    payload = {
        "contents": [
            {"parts": [{"text": prompt}]}
        ],
        "generationConfig": {
            "temperature": 0.2,
            "response_mime_type": "application/json"
        }
    }

    try:
        resp = httpx.post(url, params={"key": GEMINI_API_KEY}, json=payload, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        candidates = data.get("candidates", [])
        if not candidates:
            return None
        parts = candidates[0].get("content", {}).get("parts", [])
        if not parts:
            return None

        result = parts[0].get("text", "").strip()
        result = re.sub(r"^```json\s*", "", result, flags=re.IGNORECASE)
        result = re.sub(r"\s*```$", "", result, flags=re.IGNORECASE).strip()
        return result
    except Exception:
        return None

def add_vietnamese_meaning(word: str, english_definition: str, example: str) -> Dict[str, Any]:
    vi = translate_with_gemini(english_definition) or english_definition
    return {
        "word": word,
        "meaning": vi,
        "example": example
    }

def fetch_word_from_english_api(word: str) -> Optional[Dict[str, Any]]:
    url = ENGLISH_API.format(word=normalize_word(word))
    try:
        resp = httpx.get(url, timeout=20)
        if resp.status_code != 200:
            return None
        data = resp.json()
        if not isinstance(data, list) or not data:
            return None

        entry = data[0]
        meanings = entry.get("meanings", [])
        if not meanings:
            return None

        definition = get_first_definition(meanings)
        example = get_first_example(meanings)
        synonyms, antonyms = get_synonyms_antonyms(meanings)
        pos = get_part_of_speech(meanings)

        phonetic = ""
        if "phonetics" in entry and entry["phonetics"]:
            for ph in entry["phonetics"]:
                if ph.get("text"):
                    phonetic = ph["text"]
                    break

        if not definition:
            return None

        translated = translate_with_gemini(definition)
        if not translated:
            translated = definition

        result = {
            "word": entry.get("word", word),
            "phonetic": phonetic,
            "part_of_speech": pos,
            "meaning": translated,
            "example": example,
            "synonyms": synonyms,
            "antonyms": antonyms,
            "topic": "general",
            "level": "A1"
        }
        return result
    except Exception:
        return None

def save_to_json(records: List[Dict[str, Any]], path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)

def save_to_mongodb(records: List[Dict[str, Any]]):
    if not MONGO_URI:
        return False

    client = MongoClient(MONGO_URI)
    db = client[MONGO_DB_NAME]
    collection = db["vocabularies"]

    inserted = 0
    for record in records:
        word = normalize_word(record["word"])
        existing = collection.find_one({"word_key": word})
        if not existing:
            collection.insert_one({
                "word": word,
                "word_key": word,
                "phonetic": record.get("phonetic", ""),
                "part_of_speech": record.get("part_of_speech", ""),
                "meaning": record.get("meaning", ""),
                "example": record.get("example", ""),
                "synonyms": record.get("synonyms", []),
                "antonyms": record.get("antonyms", []),
                "topic": record.get("topic", "general"),
                "level": record.get("level", "A1"),
                "created_at": __import__("datetime").datetime.utcnow(),
                "updated_at": __import__("datetime").datetime.utcnow()
            })
            inserted += 1

    print(f"Inserted into MongoDB: {inserted}")
    return True

def import_words(words: List[str], topic: str = "general", level: str = "A1", save_json: bool = True, save_mongo: bool = True):
    records = []

    for raw_word in words:
        word = normalize_word(raw_word)
        if not word:
            continue

        data = fetch_word_from_english_api(word)
        if not data:
            print(f"Skipping {word}: no data from English API")
            continue

        data["topic"] = topic
        data["level"] = level

        records.append(data)

    if save_json:
        save_to_json(records, OUTPUT_JSON_PATH)
        print(f"Saved JSON: {OUTPUT_JSON_PATH}")

    if save_mongo:
        save_to_mongodb(records)

    return records

# -----------------------------
# Example usage
# -----------------------------
if __name__ == "__main__":
    words = [
        "happy",
        "environment",
        "opportunity",
        "improve",
        "knowledge",
        "technology",
        "travel",
        "success",
        "challenge",
        "customer"
    ]

    results = import_words(
        words=words,
        topic="daily-life",
        level="A1",
        save_json=True,
        save_mongo=True
    )

    print(json.dumps(results[:2], ensure_ascii=False, indent=2))