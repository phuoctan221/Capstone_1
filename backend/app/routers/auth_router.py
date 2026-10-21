from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status

from app.models.user import UserCreate, UserLogin, Token
from app.services import auth_service
from app.db.mongodb import get_database

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=Token, status_code=status.HTTP_201_CREATED)
async def register(data: UserCreate):
    db = get_database()
    existing = await db.users.find_one({"email": data.email})
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Email already registered"
        )

    now = datetime.now(timezone.utc)
    user_doc = {
        "_id": data.email,
        "email": data.email,
        "username": data.username,
        "password_hash": auth_service.hash_password(data.password),
        "created_at": now,
    }
    await db.users.insert_one(user_doc)

    token = auth_service.create_access_token(data.email)
    return Token(
        access_token=token,
        user={
            "id": data.email,
            "email": data.email,
            "username": data.username,
            "created_at": now,
        },
    )


@router.post("/login", response_model=Token)
async def login(data: UserLogin):
    db = get_database()
    user = await db.users.find_one({"email": data.email})
    if not user or not auth_service.verify_password(
        data.password, user["password_hash"]
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )

    token = auth_service.create_access_token(data.email)
    return Token(
        access_token=token,
        user={
            "id": str(user["_id"]),
            "email": user["email"],
            "username": user["username"],
            "created_at": user.get("created_at", datetime.now(timezone.utc)),
        },
    )
