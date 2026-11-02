from fastapi import APIRouter, Depends

from app.models.learning import ReviewRequest, ReviewStats
from app.services import learning_service
from app.services.auth_service import get_current_user

router = APIRouter(prefix="/learning", tags=["learning"])


@router.get("/due")
async def due_cards(user: dict = Depends(get_current_user)):
    return await learning_service.get_due_cards(user["id"])


@router.post("/review")
async def review(data: ReviewRequest, user: dict = Depends(get_current_user)):
    return await learning_service.review_card(
        user_id=user["id"],
        vocabulary_id=data.vocabulary_id,
        remembered=data.remembered,
    )


@router.get("/stats", response_model=ReviewStats)
async def stats(user: dict = Depends(get_current_user)):
    return await learning_service.get_stats(user["id"])
