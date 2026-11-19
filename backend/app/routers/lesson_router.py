import logging

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query

from app.models.lesson import BatchMistakeAnalysisRequest, QuizResultOut, QuizSubmit
from app.services import ai_service, lesson_service, quiz_service, progress_service
from app.services.ai_rate_limit import limit
from app.services.auth_service import get_current_user

router = APIRouter(prefix="/lessons", tags=["lessons"])
logger = logging.getLogger("uvicorn.error")


@router.get("")
async def list_lessons(user: dict = Depends(get_current_user)):
    return await lesson_service.list_lessons(user["id"])


@router.get("/{lesson_id}")
async def get_lesson(
    lesson_id: str,
    unit: int | None = Query(None, ge=1),
    user: dict = Depends(get_current_user),
):
    try:
        lesson = await lesson_service.get_lesson(lesson_id, user["id"], unit)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not lesson:
        raise HTTPException(status_code=404, detail="Lesson not found")
    return lesson


@router.get("/{lesson_id}/quiz")
async def get_quiz(
    lesson_id: str,
    count: int = Query(10, ge=3, le=50),
    unit: int | None = Query(None, ge=1),
    user: dict = Depends(get_current_user),
):
    try:
        questions = await quiz_service.build_quiz(
            lesson_id, user["id"], count, unit
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not questions:
        raise HTTPException(status_code=404, detail="Not enough words for a quiz")
    return {
        "lesson_id": lesson_id,
        "unit": unit,
        "questions": questions,
    }


@router.post("/quiz/analyze-all-mistakes")
async def analyze_all_quiz_mistakes(
    payload: BatchMistakeAnalysisRequest,
    user: dict = Depends(get_current_user),
):
    """Analyze submitted incorrect answers without making quiz grading depend on AI."""
    await limit(user["id"])
    db = progress_service.get_database()
    analyses: list[dict | None] = []

    for mistake in payload.mistakes:
        vocabulary = None
        if mistake.vocabulary_id and ObjectId.is_valid(mistake.vocabulary_id):
            vocabulary = await db.vocabularies.find_one(
                {"_id": ObjectId(mistake.vocabulary_id)}
            )

        try:
            analyses.append(
                await ai_service.generate_error_analysis(
                    question=mistake.question,
                    correct_answer=mistake.correct_answer,
                    user_answer=mistake.user_answer,
                    vocabulary=vocabulary or {},
                )
            )
        except Exception as exc:  # AI must never prevent the learner seeing quiz feedback.
            logger.warning(
                "Quiz error analysis failed for user=%s vocabulary=%s: %s",
                user["id"],
                mistake.vocabulary_id,
                type(exc).__name__,
            )
            analyses.append(None)

    return {"analyses": analyses}


@router.post("/{lesson_id}/quiz/submit")
async def submit_quiz(
    lesson_id: str,
    payload: QuizSubmit,
    unit: int | None = Query(None, ge=1),
    user: dict = Depends(get_current_user),
):
    total = len(payload.results)
    if total == 0:
        raise HTTPException(status_code=400, detail="Empty quiz submission")

    # Questions are stored server-side; the client cannot declare correctness.
    db = progress_service.get_database()
    correct = 0
    xp_gained = 0
    details = []
    processed_tokens = set()
    for item in payload.results:
        if item.question_token in processed_tokens:
            raise HTTPException(status_code=400, detail="Duplicate quiz question token")
        processed_tokens.add(item.question_token)

        question = await db.quiz_questions.find_one({
            "question_id": item.question_token,
            "user_id": user["id"],
            "lesson_id": lesson_id,
        })
        if not question:
            raise HTTPException(status_code=400, detail="Invalid quiz question")
        from datetime import datetime, timezone
        expires = question.get("expires_at")
        if not expires:
            raise HTTPException(status_code=400, detail="Quiz question has no expiration time")
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        if expires <= datetime.now(timezone.utc):
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
        details.append(
            {
                "vocabulary_id": item.vocabulary_id,
                "question": question.get("question", ""),
                "options": question.get("options", []),
                "correct": bool(outcome["correct"]),
                "correct_answer": outcome["correct_answer"],
                "user_answer": item.user_answer,
                "word": question.get("word"),
                "phonetic": question.get("phonetic"),
                "meaning": question.get("meaning"),
                "example": question.get("example"),
            }
        )

    percent = round(correct / total * 100)
    passed = percent >= 70
    if passed:
        try:
            lesson = await lesson_service.get_lesson(
                lesson_id, user["id"], unit
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if lesson:
            try:
                await progress_service.complete_lesson(
                    user["id"],
                    lesson_id,
                    lesson["topic"],
                    True,
                    lesson.get("learned_count", 0),
                    lesson.get("mastered_count", 0),
                    unit=lesson.get("unit"),
                )
            except ValueError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from exc

    progress = await progress_service.get_user_progress(user["id"])
    return QuizResultOut(
        correct=correct,
        total=total,
        percent=percent,
        xp_gained=xp_gained,
        passed=passed,
        new_level=progress["level"],
        new_xp=progress["xp"],
        streak=progress["streak"],
        results=details,
        wrong_count=total - correct,
    )
