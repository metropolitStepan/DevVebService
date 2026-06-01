from decimal import Decimal

from fastapi import Depends

from app.db.repositories.wallet import WalletRepository, get_wallet_repository
from app.schemas.wallet import TopupResponse, WalletBalanceResponse
from app.services.errors import NotFoundError


class WalletService:
    def __init__(self, wallet_repo: WalletRepository) -> None:
        self.wallet_repo = wallet_repo

    async def get_balance(self, user_id: int) -> WalletBalanceResponse:
        wallet = self.wallet_repo.get_wallet(user_id)
        if wallet is None:
            raise NotFoundError("WALLET_NOT_FOUND", "Wallet not found")

        return WalletBalanceResponse(
            wallet_id=wallet.id,
            user_id=wallet.user_id,
            currency_code=wallet.currency_code,
            balance=wallet.balance,
            updated_at=wallet.updated_at,
        )

    async def topup(
        self,
        *,
        user_id: int,
        amount: Decimal,
        reason: str,
        external_ref: str | None,
    ) -> TopupResponse:
        topup = self.wallet_repo.topup(
            user_id=user_id,
            amount=amount,
            reason=reason,
            external_ref=external_ref,
        )
        return TopupResponse(
            id=topup.id,
            wallet_id=topup.wallet_id,
            amount=topup.amount,
            status=topup.status,
            reason=topup.reason,
            external_ref=topup.external_ref,
            created_at=topup.created_at,
            applied_at=topup.applied_at,
        )


def get_wallet_service(wallet_repo: WalletRepository = Depends(get_wallet_repository)) -> WalletService:
    return WalletService(wallet_repo=wallet_repo)
