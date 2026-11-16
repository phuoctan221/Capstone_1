"""Chivox MCP adapter. Credentials and upstream authentication metadata never leave here."""
import asyncio
import base64
import json
import math
import os
import subprocess

import httpx
from fastapi import HTTPException

from app.core.config import settings

ENDPOINT = "https://mcp-global.cloud.chivox.com/"


def prepare_mp3(audio: bytes, mime: str, max_seconds: int) -> bytes:
    formats = {"audio/webm": "matroska", "audio/ogg": "ogg", "audio/mp4": "mov", "audio/wav": "wav"}
    mime = mime.split(";")[0].lower()
    if mime not in formats:
        raise HTTPException(415, "Định dạng âm thanh chưa được hỗ trợ.")
    if not 100 <= len(audio) <= 5 * 1024 * 1024:
        raise HTTPException(400, "Âm thanh trống hoặc lớn hơn 5 MB.")
    flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
    def run(args, content):
        return subprocess.run([settings.FFMPEG_PATH, "-nostdin", "-v", "error", *args],
                              input=content, capture_output=True, timeout=20, check=True,
                              creationflags=flags).stdout
    try:
        pcm = run(["-protocol_whitelist", "pipe", "-f", formats[mime], "-i", "pipe:0",
                   "-t", str(max_seconds + 1), "-vn", "-ar", "16000", "-ac", "1", "-f", "s16le", "pipe:1"], audio)
        duration = len(pcm) / 32000
        if duration < 0.2 or duration > max_seconds:
            raise HTTPException(422, f"Bản ghi cần dài từ 0,2 đến {max_seconds} giây. Hãy thu âm lại.")
        return run(["-f", "s16le", "-ar", "16000", "-ac", "1", "-i", "pipe:0", "-codec:a", "libmp3lame", "-b:a", "64k", "-f", "mp3", "pipe:1"], pcm)
    except FileNotFoundError:
        raise HTTPException(503, "Tạm thời chưa thể đánh giá. Bạn vui lòng thử lại sau nhé.") from None
    except (subprocess.SubprocessError, OSError):
        raise HTTPException(422, "Không đọc được bản ghi âm. Hãy thu âm lại.") from None


def rpc_body(response):
    if response.status_code in (401, 403):
        raise HTTPException(503, "Tạm thời chưa thể đánh giá. Bạn vui lòng thử lại sau nhé.")
    if response.status_code == 429:
        raise HTTPException(503, "Tạm thời chưa thể đánh giá. Bạn vui lòng thử lại sau nhé.")
    if not response.is_success:
        raise HTTPException(502, "Tạm thời chưa thể đánh giá. Bạn vui lòng thử lại sau nhé.")
    try:
        if "text/event-stream" in response.headers.get("content-type", ""):
            # This endpoint normally returns JSON; also accept complete SSE data events.
            events = response.text.replace("\r\n", "\n").split("\n\n")
            payload = next(json.loads("\n".join(line[5:].strip() for line in event.splitlines() if line.startswith("data:")))
                           for event in events if any(line.startswith("data:") for line in event.splitlines()))
        else:
            payload = response.json()
        if not isinstance(payload, dict) or payload.get("error"):
            raise ValueError()
        return payload
    except (ValueError, StopIteration):
        raise HTTPException(502, "Tạm thời chưa thể đánh giá. Bạn vui lòng thử lại sau nhé.") from None


def number(value):
    return value if type(value) in (int, float) and math.isfinite(value) and 0 <= value <= 100 else None


def normalize(text, payload):
    if not isinstance(payload, dict) or payload.get("error") or payload.get("errId"):
        raise HTTPException(502, "Tạm thời chưa thể đánh giá. Bạn vui lòng thử lại sau nhé.")
    score = payload.get("result", payload)
    if not isinstance(score, dict) or number(score.get("overall")) is None:
        raise HTTPException(502, "Tạm thời chưa thể đánh giá. Bạn vui lòng thử lại sau nhé.")
    info = score.get("info") or {}
    invalid = bool(score.get("forceout")) or score.get("wavetime") == 0
    details = score.get("details") or {}
    raw_words = details.get("word", []) if isinstance(details, dict) else details
    words = []
    for word in raw_words:
        phones = word.get("phone") or word.get("phn") or []
        words.append({"word": word.get("name") or word.get("char") or text,
                      "quality_score": None if invalid else number(word.get("score")),
                      "error_code": word.get("is_err"),
                      "phone_score_list": [{"phone": p.get("lab") or p.get("phoneme"),
                                            "quality_score": number(p.get("score")),
                                            "recognized_phone": p.get("rec"), "error_code": p.get("is_err")}
                                           for p in phones]})
    warning = ""
    if invalid:
        warning = "Bạn chưa đọc đúng từ/cụm từ. Hãy đọc lại nhé."
    elif info.get("tipId") not in (None, 0):
        warning = "Chưa nghe rõ giọng đọc của bạn. Hãy đọc lại ở nơi yên tĩnh nhé."
    return {"provider": "chivox", "text": text, "status": "retry" if invalid else "scored",
            "overall": None if invalid else number(score.get("overall")),
            "pronunciation": None if invalid else number(score.get("pron")),
            "words": words, "warning": warning,
            # Only assessment fields, never upstream app/sig/token/audio URL envelopes.
            "assessment_details": {key: score[key] for key in ("overall", "pron", "accuracy", "integrity", "fluency", "details", "info", "forceout", "wavetime") if key in score}}


async def score_audio(text, audio, mime):
    if not settings.CHIVOX_API_KEY:
        raise HTTPException(503, "Tạm thời chưa thể đánh giá. Bạn vui lòng thử lại sau nhé.")
    single_word = len(text.split()) == 1
    mp3 = await asyncio.to_thread(prepare_mp3, audio, mime, 19 if single_word else 30)
    headers = {"Authorization": f"Bearer {settings.CHIVOX_API_KEY}", "Accept": "application/json, text/event-stream"}
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(ENDPOINT, headers=headers, json={"jsonrpc": "2.0", "id": 1, "method": "initialize",
                "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "smartvocab", "version": "1.0"}}})
            rpc_body(response)
            session_id = response.headers.get("mcp-session-id")
            if session_id:
                headers["Mcp-Session-Id"] = session_id
            try:
                notice = await client.post(ENDPOINT, headers=headers, json={"jsonrpc": "2.0", "method": "notifications/initialized"})
                if not notice.is_success:
                    raise HTTPException(502, "Tạm thời chưa thể đánh giá. Bạn vui lòng thử lại sau nhé.")
                response = await client.post(ENDPOINT, headers=headers, json={"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                    "params": {"name": "en_word_correction" if single_word else "en_sentence_correction", "arguments": {
                        "ref_text": text, "audio_base64": base64.b64encode(mp3).decode("ascii"),
                        "accent": 2, "rank": 100, "attachAudioUrl": 0}}})
                result = rpc_body(response).get("result", {})
                if result.get("isError"):
                    raise HTTPException(502, "Tạm thời chưa thể đánh giá. Bạn vui lòng thử lại sau nhé.")
                raw = next(item["text"] for item in result.get("content", []) if item.get("type") == "text")
                return normalize(text, json.loads(raw))
            finally:
                if session_id:
                    try:
                        await client.delete(ENDPOINT, headers=headers, timeout=5)
                    except httpx.HTTPError:
                        pass
    except (httpx.HTTPError, ValueError, KeyError, TypeError, AttributeError, StopIteration):
        raise HTTPException(502, "Tạm thời chưa thể đánh giá. Bạn vui lòng thử lại sau nhé.") from None
