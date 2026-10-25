import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.models.vocabulary import (
    VocabularyCreate,
    VocabularyUpdate,
    VocabularyOut,
    AIGenerateRequest,
    AIGenerateResponse,
    AIBatchRequest,
    AIBatchResponse,
    AIBatchItem,
)
from app.services import vocabulary_service, ai_service
from app.services.auth_service import get_current_user

logger = logging.getLogger("uvicorn.error")

router = APIRouter(prefix="/vocabulary", tags=["vocabulary"])


@router.get("")
async def list_vocabularies(
    topic: str | None = None,
    level: str | None = None,
    search: str | None = Query(None, max_length=100),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    _: dict = Depends(get_current_user),
):
    return await vocabulary_service.list_vocabularies(
        topic=topic, level=level, search=search, page=page, page_size=page_size
    )


@router.get("/{vocab_id}", response_model=VocabularyOut)
async def get_vocabulary(vocab_id: str, _: dict = Depends(get_current_user)):
    vocab = await vocabulary_service.get_vocabulary(vocab_id)
    if not vocab:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return vocab


@router.post("", response_model=VocabularyOut, status_code=status.HTTP_201_CREATED)
async def create_vocabulary(
    data: VocabularyCreate, _: dict = Depends(get_current_user)
):
    return await vocabulary_service.create_vocabulary(data)


@router.put("/{vocab_id}", response_model=VocabularyOut)
async def update_vocabulary(
    vocab_id: str, data: VocabularyUpdate, _: dict = Depends(get_current_user)
):
    vocab = await vocabulary_service.update_vocabulary(vocab_id, data)
    if not vocab:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return vocab


@router.delete("/{vocab_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_vocabulary(vocab_id: str, _: dict = Depends(get_current_user)):
    deleted = await vocabulary_service.delete_vocabulary(vocab_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")


@router.post("/ai-generate", response_model=AIGenerateResponse)
async def ai_generate(data: AIGenerateRequest, _: dict = Depends(get_current_user)):
    try:
        return await ai_service.generate_vocabulary(
            word=data.word, target_language=data.target_language
        )
    except Exception as exc:
        logger.exception("AI generation failed cho word=%r", data.word)
        detail = f"{type(exc).__name__}: {exc}".strip().rstrip(":")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"AI generation failed - {detail}",
        )


@router.post("/ai-generate-batch", response_model=AIBatchResponse)
async def ai_generate_batch(data: AIBatchRequest, _: dict = Depends(get_current_user)):
    """Sinh chi tiet cho nhieu tu.

    - Neu `words` rong: AI goi y danh sach tu theo topic/level truoc.
    - Cac tu duoc xu ly song song (nhom toi da 4 luoi) vi Gemini free tier rat cham.
    """
    words = [w.strip() for w in data.words if w and w.strip()]
    from_user = bool(words)

    if not words:
        try:
            words = await ai_service.suggest_words(data.topic, data.level, data.count)
        except Exception as exc:
            logger.exception("AI suggest failed cho topic=%r", data.topic)
            detail = f"{type(exc).__name__}: {exc}".strip().rstrip(":")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"AI goi y that bai - {detail}",
            )
        if not words:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="AI khong goi y duoc tu nao cho chu de nay.",
            )

    if not from_user:
        words = words[: data.count]

    logger.info("AI batch: xu ly %s tu (topic=%s level=%s)", len(words), data.topic, data.level)

    results = await ai_service.generate_vocabulary_batch(
        words, topic=data.topic, level=data.level
    )

    items: list[AIBatchItem] = []
    payload: list[dict] = []
    for result in results:
        if not result["ok"] or not result["data"]:
            items.append(AIBatchItem(word=result["word"], ok=False, error=result["error"]))
            continue
        try:
            validated = AIGenerateResponse(**result["data"])
        except Exception as exc:
            items.append(
                AIBatchItem(
                    word=result["word"],
                    ok=False,
                    error=f"Du lieu AI khong hop le: {exc}"[:300],
                )
            )
            continue
        items.append(AIBatchItem(word=result["word"], ok=True, data=validated))
        payload.append(validated.model_dump())

    saved = 0
    if data.save and payload:
        outcome = await vocabulary_service.create_vocabularies_bulk(payload)
        saved = outcome["saved"]
        logger.info("AI batch: da luu %s tu", saved)

    if items and not any(i.ok for i in items):
        first_error = items[0].error or "Khong ro ly do"
        if "AIQuotaError" in first_error:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=first_error,
            )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"AI batch that bai - {first_error}"[:400],
        )

    return AIBatchResponse(
        requested=len(items),
        succeeded=sum(1 for i in items if i.ok),
        failed=sum(1 for i in items if not i.ok),
        saved=saved,
        items=items,
    )
