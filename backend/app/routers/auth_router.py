from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from app.models.user import (
    UserCreate,
    UserLogin,
    Token,
    UserOut,
    OnboardingRequest,
    UserProfileUpdate,
    ChangePasswordRequest,
    PasswordResetRequest,
    PasswordResetVerify,
    PasswordResetConfirm,
)
from app.services import auth_service, avatar_service, lesson_service, password_reset_service
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
        "role": auth_service.normalize_role(user.get("role")),
        "created_at": user.get("created_at") or datetime.now(timezone.utc),
        "learning_level": user.get("learning_level"),
        "placement_levels": user.get("placement_levels") or {},
        "interests": user.get("interests") or [],
        "onboarded": bool(user.get("onboarded")),
        "daily_goal": user.get("daily_goal") or 10,
        "daily_new_limit": user.get("daily_new_limit") or 10,
        "daily_review_limit": user.get("daily_review_limit") or 30,
        "xp": int(user.get("xp", 0) or 0),
        "streak": int(user.get("streak", 0) or 0),
        "profile_completed_at": user.get("profile_completed_at"),
        "updated_at": user.get("updated_at"),
        "avatar_url": user.get("avatar_url"),
    }


@router.post("/register", response_model=Token, status_code=status.HTTP_201_CREATED)
async def register(data: UserCreate):
    db = get_database()
    email = data.email.strip().lower()
    existing = await db.users.find_one({"email": email})
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Email already registered"
        )

    now = datetime.now(timezone.utc)
    user_doc = {
        "_id": email,
        "email": email,
        "username": data.username.strip(),
        "password_hash": auth_service.hash_password(data.password),
        "role": "user",
        "created_at": now,
        "learning_level": None,
        "interests": [],
        "onboarded": False,
        "daily_goal": 10,
        "daily_new_limit": 10,
        "daily_review_limit": 30,
        "xp": 0,
        "streak": 0,
        "token_version": 0,
    }
    await db.users.insert_one(user_doc)

    token = auth_service.create_access_token(email, 0)
    return Token(access_token=token, user=_user_out(user_doc))


@router.post("/login", response_model=Token)
async def login(data: UserLogin):
    db = get_database()
    email = data.email.strip().lower()
    user = await db.users.find_one({"email": email})
    if not user or not auth_service.verify_password(
        data.password, user["password_hash"]
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    if user.get("is_active") is False:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Tài khoản đã bị khóa. Vui lòng liên hệ quản trị viên.",
        )

    token = auth_service.create_access_token(
        str(user["_id"]), auth_service.token_version_of(user)
    )
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
    if data.learning_level is not None:
        placement_interests = updates.get("interests", user.get("interests") or [])
        updates["placement_levels"] = lesson_service.placement_levels_for_interests(
            placement_interests, data.learning_level
        )
    if data.daily_goal is not None:
        updates["daily_goal"] = int(data.daily_goal)
    if data.daily_new_limit is not None:
        updates["daily_new_limit"] = int(data.daily_new_limit)
    if data.daily_review_limit is not None:
        updates["daily_review_limit"] = int(data.daily_review_limit)
    if data.onboarded is not None:
        updates["onboarded"] = bool(data.onboarded)
    if not updates:
        return _user_out(user)
    updates["updated_at"] = datetime.now(timezone.utc)
    await db.users.update_one({"_id": user["id"]}, {"$set": updates})
    updated = await db.users.find_one({"_id": user["id"]})
    return _user_out(updated)


@router.post("/me/avatar", response_model=UserOut)
async def upload_avatar(
    avatar: UploadFile = File(...),
    user: dict = Depends(auth_service.get_current_user),
):
    avatar_url = await avatar_service.save_avatar(avatar)
    old_avatar_url = user.get("avatar_url")
    await get_database().users.update_one(
        {"_id": user["id"]},
        {"$set": {"avatar_url": avatar_url, "updated_at": datetime.now(timezone.utc)}},
    )
    avatar_service.delete_avatar(old_avatar_url)
    updated = await get_database().users.find_one({"_id": user["id"]})
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
        "placement_levels": lesson_service.placement_levels_for_interests(
            interests, data.learning_level
        ),
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
    new_version = auth_service.token_version_of(user) + 1
    updates = {
        "password_hash": auth_service.hash_password(data.new_password),
        "token_version": new_version,
        "updated_at": datetime.now(timezone.utc),
    }
    await db.users.update_one({"_id": user["id"]}, {"$set": updates})
    # Re-issue a token for the current session so other devices are logged out
    # while this one keeps working.
    token = auth_service.create_access_token(user["id"], new_version)
    return {
        "message": "Đổi mật khẩu thành công",
        "access_token": token,
        "token_type": "bearer",
    }


@router.post("/password-reset/request")
async def request_password_reset(data: PasswordResetRequest):
    # Keep this neutral to avoid account enumeration. SMTP failures are logged by
    # deployment monitoring rather than exposed as an account-existence signal.
    try:
        await password_reset_service.request_reset(data.email)
    except Exception:
        pass
    return {"message": "If that email is registered, a verification code has been sent."}


@router.post("/password-reset/verify")
async def verify_password_reset(data: PasswordResetVerify):
    if not await password_reset_service.verify_reset(data.email, data.otp):
        raise HTTPException(status_code=400, detail="Invalid, expired, or locked verification code")
    return {"verified": True}


@router.post("/password-reset/confirm")
async def confirm_password_reset(data: PasswordResetConfirm):
    if not await password_reset_service.confirm_reset(data.email, data.otp, data.new_password):
        raise HTTPException(status_code=400, detail="Invalid, expired, or locked verification code")
    return {"message": "Password reset successfully. Please sign in again."}
