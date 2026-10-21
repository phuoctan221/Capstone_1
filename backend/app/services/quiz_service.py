import random

from app.db.mongodb import get_database
from app.services.lesson_service import get_lesson


async def build_quiz(lesson_id: str, user_id: str, count: int = 10) -> list[dict]:
    db = get_database()
    lesson = await get_lesson(lesson_id, user_id)
    if not lesson:
        return []

    words = lesson["words"]
    if len(words) < 2:
        return []

    sample = random.sample(words, min(count, len(words)))
    all_meanings = [w["meaning"] for w in words]
    all_words = [w["word"] for w in words]

    questions = []
    for w in sample:
        qtype = random.choice(["meaning", "word"])
        if qtype == "meaning":
            question = f"Từ \"{w['word']}\" có nghĩa là gì?"
            correct = w["meaning"]
            pool = [m for m in all_meanings if m != correct]
            distractors = random.sample(pool, min(3, len(pool)))
            options = distractors + [correct]
        else:
            question = f"Từ tiếng Anh nào có nghĩa: \"{w['meaning']}\"?"
            correct = w["word"]
            pool = [x for x in all_words if x != correct]
            distractors = random.sample(pool, min(3, len(pool)))
            options = distractors + [correct]

        random.shuffle(options)
        questions.append(
            {
                "vocabulary_id": w["id"],
                "question": question,
                "question_type": "multiple_choice",
                "options": options,
                "answer": correct,
            }
        )
    return questions
