# api/routes/users.py
"""User (staff) management endpoints."""

import re
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field, field_validator

from shared.audit_utils import log_audit
from shared.auth_dependencies import require_admin_user
from shared.config import get_settings
from shared.database import get_raw_pool
from shared.phone_utils import normalize_phone
from shared.sql_utils import format_sql

router = APIRouter()
settings = get_settings()

PHONE_REGEX = r"^\+7\d{10}$"
ALLOWED_ROLES = {"waiter", "cook", "manager", "admin", "user"}


class UserCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    role: str = Field(default="waiter")
    phone: Optional[str] = None
    telegram_id: Optional[str] = Field(default=None, max_length=64)
    email: Optional[str] = Field(default=None, max_length=255)

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: str) -> str:
        if v not in ALLOWED_ROLES:
            raise ValueError(f"role must be one of {ALLOWED_ROLES}")
        return v

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: Optional[str]) -> Optional[str]:
        normalized = normalize_phone(v)
        if normalized is None:
            raise ValueError("Invalid phone format. Expected +7XXXXXXXXXX")
        return normalized


class UserUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    role: Optional[str] = None
    phone: Optional[str] = None
    telegram_id: Optional[str] = Field(default=None, max_length=64)
    email: Optional[str] = Field(default=None, max_length=255)
    is_active: Optional[bool] = None

    @field_validator("role")
    @classmethod
    def validate_role(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in ALLOWED_ROLES:
            raise ValueError(f"role must be one of {ALLOWED_ROLES}")
        return v

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: Optional[str]) -> Optional[str]:
        normalized = normalize_phone(v)
        if normalized is None:
            raise ValueError("Invalid phone format. Expected +7XXXXXXXXXX")
        return normalized


@router.get("/users")
async def list_users(
    request: Request,
    include_inactive: bool = False,
) -> list[dict[str, Any]]:
    """List staff/users. Admin/owner only."""
    require_admin_user(request)
    tenant_schema: str = request.state.tenant_schema
    pool = await get_raw_pool()

    query = format_sql(
        """
        SELECT id, external_id, telegram_id, name, phone, email, role, is_active, loyalty_points, created_at
        FROM {}.users
        WHERE 1=1
        """,
        tenant_schema,
    )
    params: list[Any] = []

    if not include_inactive:
        query += " AND is_active = TRUE"

    query += " ORDER BY created_at DESC"

    rows = await pool.fetch(query, *params)
    result = []
    for row in rows:
        d = dict(row)
        d["tenant_id"] = tenant_schema.removeprefix("tenant_")
        if hasattr(d.get("created_at"), "isoformat"):
            d["created_at"] = d["created_at"].isoformat()
        result.append(d)
    return result


@router.post("/users", status_code=201)
async def create_user(request: Request, body: UserCreate) -> dict[str, Any]:
    """Create a new staff member. Admin/owner only."""
    require_admin_user(request)
    tenant_schema: str = request.state.tenant_schema
    pool = await get_raw_pool()

    row = await pool.fetchrow(
        format_sql(
            """
            INSERT INTO {}.users (name, role, phone, telegram_id, email, is_active)
            VALUES ($1, $2, $3, $4, $5, TRUE)
            RETURNING id, name, role, phone, telegram_id, email, is_active, created_at
            """,
            tenant_schema,
        ),
        body.name,
        body.role,
        body.phone,
        body.telegram_id,
        body.email,
    )

    assert row is not None
    user_id = int(row["id"])
    await log_audit(
        tenant_schema=tenant_schema,
        user_id=getattr(request.state, "user_id", None),
        action="CREATE",
        table_name="users",
        record_id=user_id,
        new_values=dict(row),
        ip_address=request.client.host if request.client else None,
    )

    d = dict(row)
    d["tenant_id"] = tenant_schema.removeprefix("tenant_")
    if hasattr(d.get("created_at"), "isoformat"):
        d["created_at"] = d["created_at"].isoformat()
    return d


@router.put("/users/{user_id}")
async def update_user(request: Request, user_id: int, body: UserUpdate) -> dict[str, Any]:
    """Update a staff member. Admin/owner only."""
    require_admin_user(request)
    tenant_schema: str = request.state.tenant_schema
    pool = await get_raw_pool()

    # Fetch old values for audit
    old_row = await pool.fetchrow(
        format_sql("SELECT * FROM {}.users WHERE id = $1", tenant_schema),
        user_id,
    )
    if not old_row:
        raise HTTPException(status_code=404, detail="User not found")

    fields: list[str] = []
    params: list[Any] = []

    if body.name is not None:
        fields.append("name = $" + str(len(params) + 1))
        params.append(body.name)
    if body.role is not None:
        fields.append("role = $" + str(len(params) + 1))
        params.append(body.role)
    if body.phone is not None:
        fields.append("phone = $" + str(len(params) + 1))
        params.append(body.phone)
    if body.telegram_id is not None:
        fields.append("telegram_id = $" + str(len(params) + 1))
        params.append(body.telegram_id)
    if body.email is not None:
        fields.append("email = $" + str(len(params) + 1))
        params.append(body.email)
    if body.is_active is not None:
        fields.append("is_active = $" + str(len(params) + 1))
        params.append(body.is_active)

    if not fields:
        raise HTTPException(status_code=422, detail="No fields to update")

    fields.append("updated_at = NOW()")
    query = format_sql(
        f"""
        UPDATE {{}}.users
        SET {', '.join(fields)}
        WHERE id = ${len(params) + 1}
        RETURNING id, external_id, telegram_id, name, phone, email, role, is_active, loyalty_points, created_at, updated_at
        """,
        tenant_schema,
    )
    params.append(user_id)

    row = await pool.fetchrow(query, *params)
    assert row is not None

    await log_audit(
        tenant_schema=tenant_schema,
        user_id=getattr(request.state, "user_id", None),
        action="UPDATE",
        table_name="users",
        record_id=user_id,
        old_values=dict(old_row),
        new_values=dict(row),
        ip_address=request.client.host if request.client else None,
    )

    d = dict(row)
    d["tenant_id"] = tenant_schema.removeprefix("tenant_")
    for ts in ("created_at", "updated_at"):
        if hasattr(d.get(ts), "isoformat"):
            d[ts] = d[ts].isoformat()
    return d


@router.delete("/users/{user_id}")
async def delete_user(request: Request, user_id: int) -> dict[str, Any]:
    """Soft-delete a staff member. Admin/owner only."""
    require_admin_user(request)
    tenant_schema: str = request.state.tenant_schema
    pool = await get_raw_pool()

    old_row = await pool.fetchrow(
        format_sql("SELECT * FROM {}.users WHERE id = $1", tenant_schema),
        user_id,
    )
    if not old_row:
        raise HTTPException(status_code=404, detail="User not found")

    row = await pool.fetchrow(
        format_sql(
            """
            UPDATE {}.users
            SET is_active = FALSE, updated_at = NOW()
            WHERE id = $1
            RETURNING id, name, role, is_active
            """,
            tenant_schema,
        ),
        user_id,
    )
    assert row is not None

    await log_audit(
        tenant_schema=tenant_schema,
        user_id=getattr(request.state, "user_id", None),
        action="DELETE",
        table_name="users",
        record_id=user_id,
        old_values=dict(old_row),
        new_values=dict(row),
        ip_address=request.client.host if request.client else None,
    )

    return {"id": user_id, "detail": "User deactivated"}
