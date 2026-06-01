from datetime import UTC

from fastapi import Depends

from app.core.config import settings
from app.core.redis import (
    acquire_purchase_reserve,
    publish_purchase_created,
    release_purchase_reserve,
)
from app.db.repositories.purchases import PurchaseRepository, get_purchase_repository
from app.schemas.purchases import PurchaseListResponse, PurchaseResponse
from app.services.errors import ConflictError, ForbiddenError


class PurchaseService:
    def __init__(self, purchase_repo: PurchaseRepository) -> None:
        self.purchase_repo = purchase_repo

    async def buy(
        self,
        *,
        user_id: int,
        item_id: int,
        quantity: int,
        idempotency_key: str,
    ) -> PurchaseResponse:
        is_reserved = await acquire_purchase_reserve(
            user_id=user_id,
            idempotency_key=idempotency_key,
            ttl_seconds=settings.purchase_reserve_ttl_seconds,
        )
        if not is_reserved:
            raise ConflictError(
                "IDEMPOTENCY_IN_PROGRESS",
                "Purchase request is already in progress",
            )

        try:
            purchase, is_new_purchase = self.purchase_repo.create_purchase(
                user_id=user_id,
                item_id=item_id,
                quantity=quantity,
                idempotency_key=idempotency_key,
            )
        finally:
            await release_purchase_reserve(user_id=user_id, idempotency_key=idempotency_key)

        if is_new_purchase:
            await publish_purchase_created(
                payload=_build_purchase_created_payload(purchase=purchase),
            )

        return _map_purchase(purchase)

    async def history(self, *, user_id: int, limit: int, offset: int) -> PurchaseListResponse:
        purchases, total = self.purchase_repo.list_purchases(user_id=user_id, limit=limit, offset=offset)
        return PurchaseListResponse(
            purchases=[_map_purchase(purchase) for purchase in purchases],
            total=total,
            limit=limit,
            offset=offset,
        )

    async def get_by_id(
        self,
        *,
        actor_user_id: int,
        actor_role: str,
        purchase_id: int,
    ) -> PurchaseResponse:
        purchase = self.purchase_repo.get_purchase(purchase_id=purchase_id)
        if actor_role != "admin" and purchase.user_id != actor_user_id:
            raise ForbiddenError("PURCHASE_FORBIDDEN", "You can access only your purchases")
        return _map_purchase(purchase)


def _map_purchase(purchase: object) -> PurchaseResponse:
    return PurchaseResponse(
        id=purchase.id,
        user_id=purchase.user_id,
        wallet_id=purchase.wallet_id,
        item_id=purchase.item_id,
        quantity=purchase.quantity,
        unit_price=purchase.unit_price,
        total_amount=purchase.total_amount,
        status=purchase.status,
        idempotency_key=purchase.idempotency_key,
        created_at=purchase.created_at,
        completed_at=purchase.completed_at,
    )


def _build_purchase_created_payload(purchase: object) -> dict[str, int | str]:
    return {
        "purchase_id": purchase.id,
        "user_id": purchase.user_id,
        "wallet_id": purchase.wallet_id,
        "item_id": purchase.item_id,
        "quantity": purchase.quantity,
        "unit_price": str(purchase.unit_price),
        "total_amount": str(purchase.total_amount),
        "status": purchase.status,
        "idempotency_key": purchase.idempotency_key,
        "created_at": purchase.created_at.astimezone(UTC).isoformat(),
        "completed_at": (
            purchase.completed_at.astimezone(UTC).isoformat()
            if purchase.completed_at is not None
            else purchase.created_at.astimezone(UTC).isoformat()
        ),
    }


def get_purchase_service(
    purchase_repo: PurchaseRepository = Depends(get_purchase_repository),
) -> PurchaseService:
    return PurchaseService(purchase_repo=purchase_repo)
