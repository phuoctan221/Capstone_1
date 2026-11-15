from fastapi import APIRouter, Depends

from app.services import domain_service
from app.services.auth_service import get_current_user

router = APIRouter(prefix="/domains", tags=["domains"])


@router.get("")
async def list_domains(_: dict = Depends(get_current_user)):
    return await domain_service.list_domains(include_inactive=False)
