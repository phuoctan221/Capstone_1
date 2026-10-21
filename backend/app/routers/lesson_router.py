from fastapi import APIRouter, Depends, HTTPException, Query

from app.models.lesson import QuizSubmit
from app.services import lesson_service, quiz_service, progress_service
from app.services.auth_service import get_current_user

router = APIRouter(prefix="/lessons", tags=["lessons"])


@router.get("")
async def list_lessons(user: dict = Depends(get_current_user)):
    return await lesson_service.list_lessons(user["id"])


@router.get("/{lesson_id}")
async def get_lesson(lesson_id: str, user: dict = Depends(get_current_user)):
    lesson = await lesson_service.get_lesson(lesson_id, user["id"])
    if not lesson:
        raise HTTPException(status_code=404, detail="Lesson not found")
    return lesson


@router.get("/{lesson_id}/quiz")
async def get_quiz(
    lesson_id: str,
    count: int = Query(10, ge=3, le=50),
    user: dict = Depends(get_current_user),
):
    questions = await quiz_service.build_quiz(lesson_id, user["id"], count)
    if not questions:
        raise HTTPException(status_code=404, detail="Not enough words for a quiz")
    return {"lesson_id": lesson_id, "questions": questions}


@router.post("/{lesson_id}/quiz/submit")
async def submit_quiz(
    lesson_id: str,
    payload: QuizSubmit,
    user: dict = Depends(get_current_user),
):
    total = len(payload.results)
    if total == 0:
        raise HTTPException(status_code=400, detail="Empty quiz submission")

    correct = sum(1 for r in payload.results if r.correct)

    for r in payload.results:
        if r.correct:
            await progress_service.mark_word_correct(user["id"], r.vocabulary_id)
        else:
            await progress_service.mark_word_wrong(user["id"], r.vocabulary_id)

    percent = round(correct / total * 100)
    passed = percent >= 70
    xp_gained = correct * progress_service.XP_PER_CORRECT
    if passed:
        xp_gained += progress_service.XP_PER_LESSON_BONUS
        lesson = await lesson_service.get_lesson(lesson_id, user["id"])
        if lesson:
            await progress_service.complete_lesson(
                user["id"], lesson["topic"], True
            )

    progress = await progress_service.add_xp(user["id"], xp_gained)

    return {
        "correct": correct,
        "total": total,
        "percent": percent,
        "xp_gained": xp_gained,
        "passed": passed,
        "new_level": progress["level"],
        "new_xp": progress["xp"],
        "streak": progress["streak"],
    }
