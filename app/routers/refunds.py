from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.core.deps import get_current_user
from app.schemas.auth import CurrentUser
from app.schemas.refunds import RefundRequestCreate, RefundResponse
from app.services.refund_service import RefundService, get_refund_service


router = APIRouter(prefix="/refunds", tags=["refunds"])


@router.post("", response_model=RefundResponse, status_code=status.HTTP_201_CREATED)
async def request_refund(
    payload: RefundRequestCreate,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[RefundService, Depends(get_refund_service)],
) -> RefundResponse:
    return await service.request_refund(
        actor_user_id=current_user.id,
        actor_role=current_user.role,
        purchase_id=payload.purchase_id,
        reason=payload.reason,
    )
