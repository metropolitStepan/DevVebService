from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, Index, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Inventory(Base):
    __tablename__ = "inventory"
    __table_args__ = (
        CheckConstraint("quantity >= 0", name="inventory_quantity_non_negative"),
        Index("idx_inventory_item_id", "item_id"),
    )

    user_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("users.id", onupdate="CASCADE", ondelete="RESTRICT"),
        primary_key=True,
    )
    item_id: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("items.id", onupdate="CASCADE", ondelete="RESTRICT"),
        primary_key=True,
    )
    quantity: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
