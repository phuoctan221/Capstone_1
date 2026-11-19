"""Mistral generation for AI Story. Keep credentials and upstream errors server-side."""
import httpx

from app.core.config import settings
from app.services.ai_service import AIServiceError


async def generate_json(prompt: str) -> str:
    if not settings.MISTRAL_API_KEY.strip():
        raise AIServiceError("Mistral is not configured")
    payload = {
        "model": settings.MISTRAL_MODEL,
        "messages": [
            {"role": "system", "content": "You write accurate English-learning stories and Vietnamese translations. Return only valid JSON matching the requested structure."},
            {"role": "user", "content": prompt},
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.6,
        "max_tokens": 3500,
        "stream": False,
    }
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(35, connect=10)) as client:
            response = await client.post("https://api.mistral.ai/v1/chat/completions",
                headers={"Authorization": f"Bearer {settings.MISTRAL_API_KEY.strip()}"}, json=payload)
        if response.status_code != 200:
            raise AIServiceError(f"Mistral HTTP {response.status_code}")
        data = response.json()
        choice = data["choices"][0]
        if choice.get("finish_reason") != "stop":
            raise AIServiceError("Mistral returned an incomplete story")
        content = choice["message"]["content"]
        if not isinstance(content, str) or not content.strip():
            raise AIServiceError("Mistral returned empty content")
        return content
    except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError):
        raise AIServiceError("Mistral request failed") from None
