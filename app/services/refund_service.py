from fastapi import Depends

from app.db.repositories.refunds import RefundRepository, get_refund_repository
from app.schemas.refunds import RefundResponse


class RefundService:
    def __init__(self, refund_repo: RefundRepository) -> None:
        self.refund_repo = refund_repo

    async def request_refund(
        self,
        *,
        actor_user_id: int,
        actor_role: str,
        purchase_id: int,
        reason: str,
    ) -> RefundResponse:
        refund = self.refund_repo.request_refund(
            actor_user_id=actor_user_id,
            purchase_id=purchase_id,
            reason=reason,
            is_admin=actor_role == "admin",
        )
        return RefundResponse(
            id=refund.id,
            purchase_id=refund.purchase_id,
            wallet_id=refund.wallet_id,
            amount=refund.amount,
            status=refund.status,
            reason=refund.reason,
            created_at=refund.created_at,
            processed_at=refund.processed_at,
        )


def get_refund_service(refund_repo: RefundRepository = Depends(get_refund_repository)) -> RefundService:
    return RefundService(refund_repo=refund_repo)
