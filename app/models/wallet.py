from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Wallet(Base):
    __tablename__ = "wallets"
    __table_args__ = (
        UniqueConstraint("id", "user_id", name="uq_wallets_id_user"),
        CheckConstraint("currency_code ~ '^[A-Z]{3}$'", name="wallets_currency"),
        CheckConstraint("balance >= 0", name="wallets_balance_non_negative"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", onupdate="CASCADE", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
    )
    currency_code: Mapped[str] = mapped_column(String(3), nullable=False, server_default="GLD")
    balance: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
