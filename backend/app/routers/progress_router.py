from fastapi import APIRouter, Depends, HTTPException, Query

from app.models.lesson import UserProgressOut, StudyAnswer
from app.services import progress_service
from app.services.auth_service import get_current_user

router = APIRouter(prefix="/progress", tags=["progress"])


@router.get("", response_model=UserProgressOut)
async def get_progress(user: dict = Depends(get_current_user)):
    return await progress_service.get_user_progress(user["id"])


@router.get("/summary")
async def summary(user: dict = Depends(get_current_user)):
    return await progress_service.get_summary(user["id"])


@router.get("/mastery")
async def mastery(user: dict = Depends(get_current_user)):
    return await progress_service.get_mastery_breakdown(user["id"])


@router.get("/history")
async def history(
    limit: int = Query(50, ge=1, le=200),
    user: dict = Depends(get_current_user),
):
    return await progress_service.get_history(user["id"], limit)


@router.post("/study-answer")
async def study_answer(payload: StudyAnswer, user: dict = Depends(get_current_user)):
    try:
        return await progress_service.process_study_answer(
            user_id=user["id"],
            vocabulary_id=payload.vocabulary_id,
            answer=payload.answer,
            skill=payload.skill,
            attempt_id=payload.attempt_id,
            response_time_ms=payload.response_time_ms,
            hint_used=payload.hint_used,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
