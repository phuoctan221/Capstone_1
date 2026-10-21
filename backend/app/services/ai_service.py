import json

import httpx

from app.core.config import settings

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


async def generate_vocabulary(word: str, target_language: str = "vi") -> dict:
    prompt = PROMPT_TEMPLATE.format(word=word)

    if not settings.GEMINI_API_KEY:
        raise RuntimeError("GEMINI_API_KEY is not configured")

    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{settings.GEMINI_MODEL}:generateContent"
    )
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.2, "response_mime_type": "application/json"},
    }

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            url, params={"key": settings.GEMINI_API_KEY}, json=payload
        )
        response.raise_for_status()
        data = response.json()

    text = data["candidates"][0]["content"]["parts"][0]["text"]
    return json.loads(text)
