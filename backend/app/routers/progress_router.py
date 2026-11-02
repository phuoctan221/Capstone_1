from fastapi import APIRouter, Depends

from app.models.lesson import UserProgressOut, StudyAnswer
from app.services import progress_service
from app.services.auth_service import get_current_user

router = APIRouter(prefix="/progress", tags=["progress"])


@router.get("", response_model=UserProgressOut)
async def get_progress(user: dict = Depends(get_current_user)):
    return await progress_service.get_user_progress(user["id"])


@router.post("/study-answer")
async def study_answer(
    payload: StudyAnswer, user: dict = Depends(get_current_user)
):
    if payload.correct:
        await progress_service.mark_word_correct(user["id"], payload.vocabulary_id)
    else:
        await progress_service.mark_word_wrong(user["id"], payload.vocabulary_id)

    xp = 10 if payload.correct else 2
    result = await progress_service.add_xp(user["id"], xp)
    return {"correct": payload.correct, "xp_gained": xp, **result}
