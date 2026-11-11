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

    # Questions are stored server-side; the client cannot declare correctness.
    db = progress_service.get_database()
    correct = 0
    xp_gained = 0
    for item in payload.results:
        question = await db.quiz_questions.find_one({
            "question_id": item.question_token,
            "user_id": user["id"],
            "lesson_id": lesson_id,
        })
        if not question:
            raise HTTPException(status_code=400, detail="Invalid quiz question")
        from datetime import datetime, timezone
        expires = question["expires_at"]
        if expires.replace(tzinfo=timezone.utc) <= datetime.now(timezone.utc):
            raise HTTPException(status_code=400, detail="Quiz question expired")
        if question["vocabulary_id"] != item.vocabulary_id:
            raise HTTPException(status_code=400, detail="Quiz question mismatch")
        try:
            outcome = await progress_service.process_study_answer(
                user_id=user["id"],
                vocabulary_id=item.vocabulary_id,
                answer=item.user_answer,
                skill=question["skill"],
                attempt_id=item.question_token,
                response_time_ms=item.response_time_ms,
                hint_used=item.hint_used,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        correct += int(outcome["correct"])
        xp_gained += outcome["xp_gained"]

    percent = round(correct / total * 100)
    passed = percent >= 70
    if passed:
        lesson = await lesson_service.get_lesson(lesson_id, user["id"])
        if lesson:
            await progress_service.complete_lesson(
                user["id"],
                lesson_id,
                lesson["topic"],
                True,
                lesson.get("learned_count", 0),
                lesson.get("mastered_count", 0),
            )

    progress = await progress_service.get_user_progress(user["id"])
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
