import logging

from fastapi import APIRouter, Depends, HTTPException, status

from app.models.chat import ChatMessageRequest, ChatMessageResponse
from app.services import ai_service, chat_service
from app.services.ai_rate_limit import limit
from app.services.auth_service import get_current_user

logger = logging.getLogger("uvicorn.error")

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/messages", response_model=ChatMessageResponse)
async def create_chat_message(
    data: ChatMessageRequest,
    user: dict = Depends(get_current_user),
):
    await limit(user["id"])
    try:
        return await chat_service.answer_message(
            message=data.message,
            history=[item.model_dump() for item in data.history],
            user=user,
            page=data.context.page,
        )
    except ai_service.AIQuotaError as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Trợ lý AI đã chạm giới hạn tạm thời. Vui lòng thử lại sau.",
        ) from exc
    except ai_service.AIServiceError as exc:
        logger.warning(
            "Learning chat failed for user=%s (error_type=%s)",
            user["id"],
            type(exc).__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Trợ lý AI tạm thời chưa phản hồi được. Vui lòng thử lại sau.",
        ) from exc