from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.models.vocabulary import (
    VocabularyCreate,
    VocabularyUpdate,
    VocabularyOut,
    AIGenerateRequest,
    AIGenerateResponse,
)
from app.services import vocabulary_service, ai_service
from app.services.auth_service import get_current_user

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
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"AI generation failed: {exc}",
        )
