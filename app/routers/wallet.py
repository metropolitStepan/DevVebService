from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.core.deps import get_current_user
from app.schemas.auth import CurrentUser
from app.schemas.wallet import TopupResponse, WalletBalanceResponse, WalletTopupRequest
from app.services.wallet_service import WalletService, get_wallet_service


router = APIRouter(prefix="/wallet", tags=["wallet"])


@router.get("", response_model=WalletBalanceResponse)
async def get_balance(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[WalletService, Depends(get_wallet_service)],
) -> WalletBalanceResponse:
    return await service.get_balance(current_user.id)


@router.post("/topup", response_model=TopupResponse, status_code=status.HTTP_201_CREATED)
async def topup(
    payload: WalletTopupRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: Annotated[WalletService, Depends(get_wallet_service)],
) -> TopupResponse:
    return await service.topup(
        user_id=current_user.id,
        amount=payload.amount,
        reason=payload.reason,
        external_ref=payload.external_ref,
    )
