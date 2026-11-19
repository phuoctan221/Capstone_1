from fastapi import APIRouter, Depends, HTTPException

from app.models.assessment import AssessmentCreate, AssessmentSubmit
from app.services import assessment_service
from app.services.auth_service import get_current_user

router = APIRouter(prefix="/assessments", tags=["assessments"])


@router.post("", status_code=201)
async def create_assessment(payload: AssessmentCreate, user: dict = Depends(get_current_user)):
    try:
        return await assessment_service.create_attempt(
            user["id"],
            payload.domain,
            payload.level,
            skip_learning=payload.skip_learning,
            placement_target=payload.placement_target,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/attempts/{attempt_id}")
async def get_assessment(attempt_id: str, user: dict = Depends(get_current_user)):
    attempt = await assessment_service.get_attempt(user["id"], attempt_id)
    if not attempt:
        raise HTTPException(status_code=404, detail="Assessment attempt not found or expired")
    return attempt


@router.get("/{domain}/{level}")
async def assessment_status(domain: str, level: str, user: dict = Depends(get_current_user)):
    return await assessment_service.status(user["id"], domain, level.upper())


@router.post("/attempts/{attempt_id}/submit")
async def submit_assessment(attempt_id: str, payload: AssessmentSubmit, user: dict = Depends(get_current_user)):
    try:
        return await assessment_service.submit_attempt(
            user["id"], attempt_id, [answer.model_dump() for answer in payload.answers]
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc