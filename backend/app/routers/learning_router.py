import asyncio

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.models.exercise import AnswerSubmit, SessionCreate
from app.models.learning import FSRSReviewRequest, ReviewStats
from app.services import daily_service, learning_service, lesson_service, progress_service, session_service
from app.services.auth_service import get_current_user

router = APIRouter(prefix="/learning", tags=["learning"])


@router.get("/due")
async def due_cards(user: dict = Depends(get_current_user)):
    return await learning_service.get_due_cards(user["id"])


@router.post("/review")
async def review(data: FSRSReviewRequest, user: dict = Depends(get_current_user)):
    if data.rating is None and data.remembered is None:
        raise HTTPException(status_code=422, detail="rating (1-4) is required")
    rating = data.rating if data.rating is not None else (3 if data.remembered else 1)
    try:
        return await learning_service.review_card(
            user_id=user["id"],
            vocabulary_id=data.vocabulary_id,
            rating=rating,
            review_id=data.review_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/stats", response_model=ReviewStats)
async def stats(user: dict = Depends(get_current_user)):
    return await learning_service.get_stats(user["id"])


@router.get("/daily")
async def daily_plan(
    tz_offset: int = Query(0, ge=-720, le=840),
    user: dict = Depends(get_current_user),
):
    try:
        return await daily_service.get_daily_plan(user["id"], tz_offset=tz_offset)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/dashboard")
async def dashboard(
    tz_offset: int = Query(0, ge=-720, le=840),
    user: dict = Depends(get_current_user),
):
    """Load all learner dashboard data with one authenticated request."""
    user_id = user["id"]
    progress, stats, lessons, daily = await asyncio.gather(
        progress_service.get_user_progress(user_id, user=user),
        learning_service.get_stats(user_id),
        lesson_service.list_lessons(user_id, user=user),
        daily_service.get_daily_plan(user_id, tz_offset=tz_offset, user=user),
    )
    return {
        "progress": progress,
        "stats": stats,
        "lessons": lessons,
        "daily": daily,
    }


# --- Learning sessions -------------------------------------------------


@router.post("/sessions", status_code=status.HTTP_201_CREATED)
async def create_session(
    data: SessionCreate, user: dict = Depends(get_current_user)
):
    try:
        return await session_service.create_session(
            user["id"],
            data.lesson_id,
            list(data.skills),
            data.count,
            data.unit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/sessions/{session_id}")
async def get_session(session_id: str, user: dict = Depends(get_current_user)):
    session = await session_service.get_session(user["id"], session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session_service.serialize_session(session)


@router.get("/sessions/{session_id}/exercises")
async def get_session_exercises(
    session_id: str, user: dict = Depends(get_current_user)
):
    session = await session_service.get_session_exercises(user["id"], session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@router.post("/sessions/{session_id}/answers")
async def submit_session_answer(
    session_id: str,
    payload: AnswerSubmit,
    user: dict = Depends(get_current_user),
):
    try:
        return await session_service.submit_answer(
            user_id=user["id"],
            session_id=session_id,
            exercise_item_id=payload.exercise_item_id,
            answer=payload.answer,
            attempt_id=payload.attempt_id,
            response_time_ms=payload.response_time_ms,
            hint_used=payload.hint_used,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/sessions/{session_id}/finish")
async def finish_session(session_id: str, user: dict = Depends(get_current_user)):
    try:
        return await session_service.finish_session(user["id"], session_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
