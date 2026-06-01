from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, status

from app.core.deps import get_current_user
from app.schemas.auth import CurrentUser
from app.schemas.purchases import PurchaseCreateRequest, PurchaseListResponse, PurchaseResponse
from app.services.purchase_service import PurchaseService, get_purchase_service


router = APIRouter(prefix="/purchases", tags=["purchases"])


@router.post("", response_model=PurchaseResponse, status_code=status.HTTP_201_CREATED)
async def buy(
    payload: PurchaseCreateRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[PurchaseService, Depends(get_purchase_service)],
    idempotency_key: UUID = Header(..., alias="Idempotency-Key"),
) -> PurchaseResponse:
    return await service.buy(
        user_id=current_user.id,
        item_id=payload.item_id,
        quantity=payload.quantity,
        idempotency_key=str(idempotency_key),
    )


@router.get("", response_model=PurchaseListResponse)
async def history(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[PurchaseService, Depends(get_purchase_service)],
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> PurchaseListResponse:
    return await service.history(user_id=current_user.id, limit=limit, offset=offset)


@router.get("/{purchase_id}", response_model=PurchaseResponse)
async def get_purchase(
    purchase_id: int,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[PurchaseService, Depends(get_purchase_service)],
) -> PurchaseResponse:
    return await service.get_by_id(
        actor_user_id=current_user.id,
        actor_role=current_user.role,
        purchase_id=purchase_id,
    )
