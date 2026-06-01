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
from app.models.enums import TopUpStatus


class TopUp(Base):
    __tablename__ = "topups"
    __table_args__ = (
        CheckConstraint("amount > 0", name="topups_amount_positive"),
        CheckConstraint(
            """
            (
                status = 'applied' AND applied_at IS NOT NULL
            )
            OR
            (
                status IN ('pending', 'canceled') AND applied_at IS NULL
            )
            """,
            name="topups_status_applied_at",
        ),
        Index("idx_topups_wallet_created_at_desc", "wallet_id", "created_at"),
        Index("idx_topups_status_created_at_desc", "status", "created_at"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    wallet_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("wallets.id", onupdate="CASCADE", ondelete="RESTRICT"),
        nullable=False,
    )
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    status: Mapped[TopUpStatus] = mapped_column(
        Enum(TopUpStatus, name="topup_status"), nullable=False, server_default=TopUpStatus.PENDING.value
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    external_ref: Mapped[str | None] = mapped_column(String(128), nullable=True, unique=True)
    created_by: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("users.id", onupdate="CASCADE", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
