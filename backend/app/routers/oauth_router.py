"""Authorization-code login with browser-bound, single-use state and PKCE."""
import base64
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Literal
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, Field
from pymongo.errors import DuplicateKeyError

from app.core.config import settings
from app.db.mongodb import get_database
from app.models.user import Token
from app.routers.auth_router import _user_out
from app.services.auth_service import create_access_token

router = APIRouter(prefix="/auth/oauth", tags=["auth"])
Provider = Literal["google"]
PROVIDERS = {
    "google": ("https://accounts.google.com/o/oauth2/v2/auth", "https://oauth2.googleapis.com/token", "openid email profile"),
}


class ExchangeRequest(BaseModel):
    code: str = Field(min_length=1, max_length=4096)
    state: str = Field(min_length=1, max_length=128)
    browser_secret: str = Field(min_length=32, max_length=128)


def credentials(provider):
    client_id = getattr(settings, f"{provider.upper()}_CLIENT_ID")
    secret = getattr(settings, f"{provider.upper()}_CLIENT_SECRET")
    if not client_id or not secret:
        raise HTTPException(503, f"Đăng nhập {provider.title()} chưa được cấu hình.")
    return client_id, secret


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


@router.post("/{provider}/start")
async def start(provider: Provider, response: Response):
    client_id, _ = credentials(provider)
    state, browser_secret, verifier = (secrets.token_urlsafe(32) for _ in range(3))
    redirect_uri = f"{settings.FRONTEND_URL.rstrip('/')}/auth/callback/{provider}"
    await get_database().oauth_states.insert_one({
        "_id": state, "provider": provider, "browser_hash": digest(browser_secret),
        "verifier": verifier, "redirect_uri": redirect_uri,
        "expires_at": datetime.now(timezone.utc) + timedelta(minutes=10),
    })
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    query = urlencode({"client_id": client_id, "redirect_uri": redirect_uri,
                       "response_type": "code", "scope": PROVIDERS[provider][2],
                       "state": state, "code_challenge": challenge, "code_challenge_method": "S256"})
    response.headers["Cache-Control"] = "no-store"
    return {"authorization_url": f"{PROVIDERS[provider][0]}?{query}",
            "state": state, "browser_secret": browser_secret}


async def provider_identity(provider, code, transaction):
    client_id, secret = credentials(provider)
    async with httpx.AsyncClient(timeout=15) as client:
        result = await client.post(PROVIDERS[provider][1], data={
            "client_id": client_id, "client_secret": secret, "code": code,
            "grant_type": "authorization_code", "redirect_uri": transaction["redirect_uri"],
            "code_verifier": transaction["verifier"],
        }, headers={"Accept": "application/json"})
        result.raise_for_status()
        token = result.json().get("access_token")
        if not token:
            raise HTTPException(400, "Mã đăng nhập không hợp lệ hoặc đã hết hạn. Vui lòng thử lại.")
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
        url = "https://openidconnect.googleapis.com/v1/userinfo"
        result = await client.get(url, headers=headers)
        result.raise_for_status()
        profile = result.json()
        subject = profile.get("sub")
        email = None
        if profile.get("email_verified") is True:
            email = profile.get("email")
        if not subject or not isinstance(email, str) or "@" not in email:
            raise HTTPException(400, "Tài khoản cần có email đã xác minh để đăng nhập.")
        return str(subject), email.strip().lower(), profile.get("name") or profile.get("login") or email.split("@")[0]


@router.post("/{provider}/exchange", response_model=Token)
async def exchange(provider: Provider, data: ExchangeRequest, response: Response):
    credentials(provider)
    db = get_database()
    transaction = await db.oauth_states.find_one_and_delete({
        "_id": data.state, "provider": provider, "browser_hash": digest(data.browser_secret),
        "expires_at": {"$gt": datetime.now(timezone.utc)},
    })
    if not transaction:
        raise HTTPException(400, "Phiên đăng nhập không hợp lệ hoặc đã hết hạn. Vui lòng thử lại.")
    try:
        subject, email, name = await provider_identity(provider, data.code, transaction)
    except (httpx.HTTPError, ValueError, TypeError, KeyError):
        raise HTTPException(502, "Không thể xác thực với nhà cung cấp. Vui lòng thử lại.") from None
    # Stable provider identity prevents account switching when an email changes.
    identity = f"{provider}:{subject}"
    user = await db.users.find_one({"oauth_identity": identity})
    if not user:
        user = {"_id": email, "email": email, "oauth_identity": identity,
                "username": str(name)[:30], "created_at": datetime.now(timezone.utc),
                "learning_level": None, "interests": [], "onboarded": False, "daily_goal": 10}
        try:
            await db.users.insert_one(user)
        except DuplicateKeyError:
            user = await db.users.find_one({"oauth_identity": identity})
            if not user:
                raise HTTPException(409, "Email này đã có tài khoản. Vui lòng dùng phương thức đăng nhập ban đầu.") from None
    response.headers["Cache-Control"] = "no-store"
    return Token(access_token=create_access_token(str(user["_id"])), user=_user_out(user))
