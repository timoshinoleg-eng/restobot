"""Tenant-scoped authentication models."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Index, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from shared.database import Base


class Role(Base):  # type: ignore[misc]
    """Tenant-scoped role definition."""

    __tablename__ = "roles"

    code: Mapped[str] = mapped_column(String(32), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)


class RolePermission(Base):  # type: ignore[misc]
    """Maps a role to a permission string."""

    __tablename__ = "role_permissions"
    __table_args__ = (
        UniqueConstraint("permission_code", name="uq_role_permissions_permission_code"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    role_code: Mapped[str] = mapped_column(ForeignKey("roles.code", ondelete="CASCADE"), nullable=False)
    permission_code: Mapped[str] = mapped_column(String(64), nullable=False)


class EmployeeUser(Base):  # type: ignore[misc]
    """Employee user that accesses the admin panel."""

    __tablename__ = "employee_users"
    __table_args__ = (
        UniqueConstraint("email", name="uq_employee_users_email"),
        Index("ix_employee_users_role_code", "role_code"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str | None] = mapped_column(String(20))
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    role_code: Mapped[str] = mapped_column(ForeignKey("roles.code"), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
