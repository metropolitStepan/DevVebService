from datetime import datetime
from decimal import Decimal
import uuid

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Computed,
    DateTime,
    Enum,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Numeric,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.enums import PurchaseStatus


class Purchase(Base):
    __tablename__ = "purchases"
    __table_args__ = (
        ForeignKeyConstraint(
            ["wallet_id", "user_id"],
            ["wallets.id", "wallets.user_id"],
            onupdate="CASCADE",
            ondelete="RESTRICT",
            name="fk_purchases_wallet_owner",
        ),
        CheckConstraint("quantity > 0", name="purchases_quantity_positive"),
        CheckConstraint("unit_price >= 0", name="purchases_unit_price_non_negative"),
        CheckConstraint(
            """
            (
                status IN ('pending', 'failed') AND completed_at IS NULL
            )
            OR
            (
                status IN ('completed', 'refunded') AND completed_at IS NOT NULL
            )
            """,
            name="purchases_status_completed_at",
        ),
        Index("idx_purchases_user_created_at_desc", "user_id", "created_at"),
        Index("idx_purchases_status_created_at_desc", "status", "created_at"),
        Index("idx_purchases_item_created_at_desc", "item_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", onupdate="CASCADE", ondelete="RESTRICT"),
        nullable=False,
    )
    wallet_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    item_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("items.id", onupdate="CASCADE", ondelete="RESTRICT"),
        nullable=False,
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 2),
        Computed("quantity * unit_price", persisted=True),
        nullable=False,
    )
    status: Mapped[PurchaseStatus] = mapped_column(
        Enum(PurchaseStatus, name="purchase_status"),
        nullable=False,
        server_default=PurchaseStatus.PENDING.value,
    )
    idempotency_key: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, default=uuid.uuid4, unique=True
    )
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
