from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.enums import RefundStatus


class Refund(Base):
    __tablename__ = "refunds"
    __table_args__ = (
        CheckConstraint("amount > 0", name="refunds_amount_positive"),
        CheckConstraint(
            """
            (
                status = 'applied' AND processed_at IS NOT NULL
            )
            OR
            (
                status IN ('pending', 'rejected') AND processed_at IS NULL
            )
            """,
            name="refunds_status_processed_at",
        ),
        Index("idx_refunds_wallet_created_at_desc", "wallet_id", "created_at"),
        Index("idx_refunds_status_created_at_desc", "status", "created_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    purchase_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("purchases.id", onupdate="CASCADE", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
    )
    wallet_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("wallets.id", onupdate="CASCADE", ondelete="RESTRICT"),
        nullable=False,
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[RefundStatus] = mapped_column(
        Enum(RefundStatus, name="refund_status"), nullable=False, server_default=RefundStatus.PENDING.value
    )
    external_ref: Mapped[str | None] = mapped_column(String(128), nullable=True, unique=True)
    processed_by: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("users.id", onupdate="CASCADE", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
