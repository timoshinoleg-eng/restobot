"""Onboarding schemas."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, EmailStr, Field

from backend.schemas.auth import TokenResponse


class OnboardingStartRequest(BaseModel):
    restaurant_name: str = Field(..., min_length=2, max_length=255)
    owner_email: EmailStr
    owner_password: str = Field(..., min_length=8, max_length=128)
    owner_name: str = Field(..., min_length=2, max_length=255)
    phone: str = Field(..., min_length=7, max_length=20)


class OnboardingStartResponse(BaseModel):
    tenant_slug: str
    onboarding_step: str
    trial_ends_at: datetime
    token: TokenResponse


class RestaurantInfoRequest(BaseModel):
    restaurant_display_name: str = Field(..., min_length=2, max_length=255)
    legal_name: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=20)
    support_email: EmailStr | None = None
    address_json: dict[str, object] = Field(default_factory=dict)
    working_hours_json: dict[str, object] = Field(default_factory=dict)


class OnboardingMenuItem(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=4000)
    price: Decimal = Field(..., gt=0)


class OnboardingMenuCategory(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    items: list[OnboardingMenuItem] = Field(..., min_length=1)


class MenuUploadRequest(BaseModel):
    categories: list[OnboardingMenuCategory] = Field(..., min_length=1)


class TelegramSetupRequest(BaseModel):
    bot_token: str = Field(..., min_length=10, max_length=255)


class PaymentSetupRequest(BaseModel):
    yookassa_shop_id: str | None = Field(default=None, max_length=128)
    yookassa_secret_key: str | None = Field(default=None, max_length=255)
    skip: bool = False


class OnboardingStepResponse(BaseModel):
    onboarding_step: str
    completed: bool = False


class TestOrderResponse(BaseModel):
    order_id: int
    order_number: str
    onboarding_step: str
