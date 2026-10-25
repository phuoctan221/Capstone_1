from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status

from app.models.user import (
    UserCreate,
    UserLogin,
    Token,
    UserOut,
    OnboardingRequest,
    UserProfileUpdate,
    ChangePasswordRequest,
)
from app.services import auth_service
from app.db.mongodb import get_database

router = APIRouter(prefix="/auth", tags=["auth"])

VALID_INTERESTS = {
    "technology",
    "business",
    "travel",
    "science",
    "academic",
    "daily-life",
    "general",
}


def _user_out(user: dict) -> dict:
    return {
        "id": str(user.get("_id") or user.get("email")),
        "email": user.get("email"),
        "username": user.get("username"),
        "created_at": user.get("created_at") or datetime.now(timezone.utc),
        "learning_level": user.get("learning_level"),
        "interests": user.get("interests") or [],
        "onboarded": bool(user.get("onboarded")),
        "daily_goal": user.get("daily_goal") or 10,
        "profile_completed_at": user.get("profile_completed_at"),
        "updated_at": user.get("updated_at"),
    }


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
        "learning_level": None,
        "interests": [],
        "onboarded": False,
        "daily_goal": 10,
    }
    await db.users.insert_one(user_doc)

    token = auth_service.create_access_token(data.email)
    return Token(access_token=token, user=_user_out(user_doc))


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
    return Token(access_token=token, user=_user_out(user))


@router.get("/me", response_model=UserOut)
async def me(user: dict = Depends(auth_service.get_current_user)):
    return _user_out(user)


@router.put("/me", response_model=UserOut)
async def update_me(
    data: UserProfileUpdate, user: dict = Depends(auth_service.get_current_user)
):
    db = get_database()
    updates = {}
    if data.username is not None:
        username = data.username.strip()
        if len(username) < 3 or any(ord(char) < 32 for char in username):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Ten hien thi phai tu 3 den 30 ky tu",
            )
        updates["username"] = username
    if data.learning_level is not None:
        updates["learning_level"] = data.learning_level
    if data.interests is not None:
        interests = []
        for interest in data.interests:
            if not isinstance(interest, str):
                continue
            value = interest.strip().lower()
            if value and value not in interests:
                interests.append(value)
        invalid = [value for value in interests if value not in VALID_INTERESTS]
        if invalid:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Linh vuc quan tam khong hop le",
            )
        if not interests:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Vui long chon it nhat mot linh vuc quan tam",
            )
        updates["interests"] = interests
    if data.daily_goal is not None:
        updates["daily_goal"] = int(data.daily_goal)
    if data.onboarded is not None:
        updates["onboarded"] = bool(data.onboarded)
    if not updates:
        return _user_out(user)
    updates["updated_at"] = datetime.now(timezone.utc)
    await db.users.update_one({"_id": user["id"]}, {"$set": updates})
    updated = await db.users.find_one({"_id": user["id"]})
    return _user_out(updated)


@router.post("/onboarding", response_model=UserOut)
async def complete_onboarding(
    data: OnboardingRequest, user: dict = Depends(auth_service.get_current_user)
):
    db = get_database()
    now = datetime.now(timezone.utc)
    interests = [i for i in data.interests if i]
    updates = {
        "learning_level": data.learning_level,
        "interests": interests,
        "onboarded": True,
        "profile_completed_at": now,
        "updated_at": now,
    }
    await db.users.update_one({"_id": user["id"]}, {"$set": updates})
    updated = await db.users.find_one({"_id": user["id"]})
    return _user_out(updated)


@router.put("/password")
async def change_password(
    data: ChangePasswordRequest, user: dict = Depends(auth_service.get_current_user)
):
    db = get_database()
    if not auth_service.verify_password(data.current_password, user.get("password_hash", "")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Mật khẩu hiện tại không chính xác",
        )
    if data.current_password == data.new_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Mật khẩu mới phải khác mật khẩu hiện tại",
        )
    updates = {
        "password_hash": auth_service.hash_password(data.new_password),
        "updated_at": datetime.now(timezone.utc),
    }
    await db.users.update_one({"_id": user["id"]}, {"$set": updates})
    return {"message": "Đổi mật khẩu thành công"}
