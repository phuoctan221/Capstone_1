from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Request

from app.db.mongodb import get_database
from app.models.speaking import SpeakingRequest, WordCheckRequest
from app.services import speaking_service
from app.services.auth_service import get_current_user

router = APIRouter(tags=["speaking"])


from app.services.ai_rate_limit import limit


@router.post("/speaking/check-word")
async def check_word(data: WordCheckRequest, user=Depends(get_current_user)):
    from app.services.word_validation_service import check_word as validate
    await limit(f"word-check:{user['id']}", max_requests=60)
    return await validate(data.word)


@router.get("/speaking/words")
async def words(user=Depends(get_current_user)):
    return await speaking_service.learned_words(user["id"])


@router.post("/speaking/exercises")
async def create(data: SpeakingRequest, user=Depends(get_current_user)):
    await limit(user["id"])
    return await speaking_service.create_exercise(user["id"], data)


@router.get("/speaking/exercises/{exercise_id}")
async def get(exercise_id: str, user=Depends(get_current_user)):
    return await speaking_service.get_exercise(user["id"], exercise_id)


@router.post("/speaking/exercises/{exercise_id}/items/{index}/score")
async def score(exercise_id: str, index: int, request: Request, user=Depends(get_current_user)):
    exercise = await speaking_service.get_exercise(user["id"], exercise_id)
    if not 0 <= index < len(exercise["items"]):
        raise HTTPException(404, "Không tìm thấy từ cần luyện.")
    await limit(user["id"])
    audio = bytearray()
    async for chunk in request.stream():
        audio.extend(chunk)
        if len(audio) > 5 * 1024 * 1024:
            raise HTTPException(413, "Âm thanh vượt quá 5 MB.")
    result = await speaking_service.score_audio(exercise["items"][index]["text"], bytes(audio), request.headers.get("content-type", ""))
    collection = get_database()["speaking_exercises"]
    query = {"_id": ObjectId(exercise_id), "user_id": user["id"]}
    await collection.update_one(query, {"$set": {f"results.{index}": result}})
    return result
