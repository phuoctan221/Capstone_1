from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query

from app.db.mongodb import get_database
from app.models.lesson import (
    QuizSubmit,
    QuizResultOut,
    MistakeAnalysisRequest,
    MistakeAnalysisOut,
    BatchMistakeAnalysisRequest,
)
from app.services import lesson_service, quiz_service, progress_service, ai_service, vocabulary_service
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


@router.post("/quiz/analyze-mistake", response_model=MistakeAnalysisOut)
async def analyze_quiz_mistake(
    payload: MistakeAnalysisRequest,
    user: dict = Depends(get_current_user),
):
    """AI phân tích và đánh giá 1 câu làm sai của học viên."""
    db = get_database()
    vocab = None
    if payload.vocabulary_id:
        try:
            vocab = await db["vocabularies"].find_one({"_id": ObjectId(payload.vocabulary_id)})
        except Exception:
            pass

    analysis = await ai_service.generate_error_analysis(
        question=payload.question,
        correct_answer=payload.correct_answer,
        user_answer=payload.user_answer,
        vocabulary=vocab,
    )
    return analysis


@router.post("/{lesson_id}/quiz/submit")
async def submit_quiz(
    lesson_id: str,
    payload: QuizSubmit,
    user: dict = Depends(get_current_user),
):
    total = len(payload.results)
    if total == 0:
        raise HTTPException(
            status_code=400,
            detail="Empty quiz submission",
        )

    db = get_database()
    correct = 0
    xp_gained = 0
    error_analysis = []
    processed_tokens = set()

    for item in payload.results:
        # Prevent duplicate question tokens in one submission.
        if item.question_token in processed_tokens:
            raise HTTPException(
                status_code=400,
                detail="Duplicate quiz question token",
            )
        processed_tokens.add(item.question_token)

        # Verify that this question belongs to this user and lesson.
        question_record = await db.quiz_questions.find_one({
            "question_id": item.question_token,
            "user_id": user["id"],
            "lesson_id": lesson_id,
        })

        if not question_record:
            raise HTTPException(
                status_code=400,
                detail="Invalid quiz question",
            )

        # Check question expiration.
        from datetime import datetime, timezone

        expires = question_record.get("expires_at")
        if not expires:
            raise HTTPException(
                status_code=400,
                detail="Quiz question has no expiration time",
            )

        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)

        if expires <= datetime.now(timezone.utc):
            raise HTTPException(
                status_code=400,
                detail="Quiz question expired",
            )

        if question_record["vocabulary_id"] != item.vocabulary_id:
            raise HTTPException(
                status_code=400,
                detail="Quiz question mismatch",
            )

        # Backend evaluates the answer and updates Mastery/XP.
        try:
            outcome = await progress_service.process_study_answer(
                user_id=user["id"],
                vocabulary_id=item.vocabulary_id,
                answer=item.user_answer,
                skill=question_record["skill"],
                attempt_id=item.question_token,
                response_time_ms=item.response_time_ms,
                hint_used=item.hint_used,
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=400,
                detail=str(exc),
            ) from exc

        is_correct = bool(outcome["correct"])
        correct += int(is_correct)
        xp_gained += int(outcome["xp_gained"])

        # AI analyzes incorrect answers only.
        if not is_correct:
            vocabulary = await db["vocabularies"].find_one({
                "_id": ObjectId(item.vocabulary_id)
            })

            if vocabulary:
                skill = question_record["skill"]

                if skill == "meaning":
                    question_text = (
                        f'Từ "{vocabulary.get("word", "")}" có nghĩa là gì?'
                    )
                else:
                    question_text = (
                        "Từ tiếng Anh nào có nghĩa: "
                        f'"{vocabulary.get("meaning", "")}"?'
                    )

                try:
                    analysis = await ai_service.generate_error_analysis(
                        question=question_text,
                        correct_answer=outcome["correct_answer"],
                        user_answer=item.user_answer,
                        vocabulary=vocabulary,
                    )

                    error_analysis.append({
                        "vocabulary_id": item.vocabulary_id,
                        "question": question_text,
                        "user_answer": item.user_answer,
                        "correct_answer": outcome["correct_answer"],
                        "analysis": analysis,
                    })

                except Exception:
                    # AI failure must not interrupt quiz submission.
                    error_analysis.append({
                        "vocabulary_id": item.vocabulary_id,
                        "question": question_text,
                        "user_answer": item.user_answer,
                        "correct_answer": outcome["correct_answer"],
                        "analysis": None,
                    })

    percent = round(correct / total * 100)
    passed = percent >= 70

    if passed:
        lesson = await lesson_service.get_lesson(
            lesson_id,
            user["id"],
        )

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
        "error_analysis": error_analysis,
    }
