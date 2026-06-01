from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, SmallInteger, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Role(Base):
    __tablename__ = "roles"
    __table_args__ = (
        CheckConstraint("code ~ '^[a-z_]{2,32}$'", name="roles_code_format"),
    )

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
