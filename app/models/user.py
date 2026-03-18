# app/models/user.py
from __future__ import annotations
from sqlalchemy import String, Boolean, DateTime, ForeignKey, Enum, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base import Base


UserRoleEnum = Enum(
    "super_admin",
    "branch_admin",
    "lab_staff",
    "cashier",
    name="user_role_enum",
)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(UserRoleEnum, nullable=False)

    branch_id: Mapped[int | None] = mapped_column(
        ForeignKey("branches.id"), nullable=True
    )

    branch = relationship("Branch")

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime, server_default=func.now())
