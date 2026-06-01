from datetime import datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    SmallInteger,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.enums import UserStatus


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("username ~ '^[A-Za-z0-9_]{3,50}$'", name="users_username_format"),
        CheckConstraint("position('@' in email) > 1", name="users_email_format"),
        CheckConstraint("char_length(password_hash) >= 60", name="users_password_hash_len"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(254), nullable=False)
    username: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role_id: Mapped[int] = mapped_column(
        SmallInteger,
        ForeignKey("roles.id", onupdate="CASCADE", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[UserStatus] = mapped_column(
        Enum(UserStatus, name="user_status"), nullable=False, server_default=UserStatus.ACTIVE.value
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    role = relationship("Role")


Index("uq_users_email_ci", func.lower(User.email), unique=True)
Index("idx_users_role_id", User.role_id)
