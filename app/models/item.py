from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, Boolean, CheckConstraint, DateTime, Index, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Item(Base):
    __tablename__ = "items"
    __table_args__ = (
        CheckConstraint("price >= 0", name="items_price_non_negative"),
        CheckConstraint("stock IS NULL OR stock >= 0", name="items_stock_non_negative"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    sku: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    price: Mapped[Decimal] = mapped_column(Numeric(18, 2), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    stock: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


Index(
    "idx_items_active_price",
    Item.is_active,
    Item.price,
    postgresql_where=Item.is_active.is_(True),
)
