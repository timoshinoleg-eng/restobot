"""Menu request/response schemas."""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CategoryCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    slug: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=4000)
    emoji: str | None = Field(default=None, max_length=16)
    sort_order: int = Field(default=100, ge=0, le=100000)


class CategoryUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    slug: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=4000)
    emoji: str | None = Field(default=None, max_length=16)
    sort_order: int | None = Field(default=None, ge=0, le=100000)
    is_active: bool | None = None


class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    slug: str
    description: str | None
    emoji: str | None
    sort_order: int
    is_active: bool


class DishCreate(BaseModel):
    category_id: int = Field(..., ge=1)
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=4000)
    price: Decimal = Field(..., gt=0)
    old_price: Decimal | None = Field(default=None, ge=0)
    weight_grams: int | None = Field(default=None, ge=0)
    calories: int | None = Field(default=None, ge=0)
    sku: str | None = Field(default=None, max_length=64)
    tags: list[str] = Field(default_factory=list)
    allergens: list[str] = Field(default_factory=list)
    is_available: bool = True
    is_popular: bool = False
    sort_order: int = Field(default=100, ge=0)

    @field_validator("old_price")
    @classmethod
    def validate_old_price(cls, value: Decimal | None, info: object) -> Decimal | None:
        if value is None:
            return value
        price = getattr(info, "data", {}).get("price") if hasattr(info, "data") else None
        if price is not None and value < price:
            raise ValueError("old_price must be greater than or equal to price")
        return value


class DishUpdate(BaseModel):
    category_id: int | None = Field(default=None, ge=1)
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=4000)
    price: Decimal | None = Field(default=None, gt=0)
    old_price: Decimal | None = Field(default=None, ge=0)
    weight_grams: int | None = Field(default=None, ge=0)
    calories: int | None = Field(default=None, ge=0)
    sku: str | None = Field(default=None, max_length=64)
    tags: list[str] | None = None
    allergens: list[str] | None = None
    is_available: bool | None = None
    is_popular: bool | None = None
    sort_order: int | None = Field(default=None, ge=0)


class DishOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    category_id: int
    slug: str
    sku: str | None
    name: str
    description: str | None
    price: Decimal
    old_price: Decimal | None
    weight_grams: int | None
    calories: int | None
    image_url: str | None
    tags: list[str]
    allergens: list[str]
    is_available: bool
    is_popular: bool
    sort_order: int


class DishImportItem(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=4000)
    price: Decimal = Field(..., gt=0)
    sku: str | None = Field(default=None, max_length=64)
    is_available: bool = True
    tags: list[str] = Field(default_factory=list)


class DishImportCategory(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    items: list[DishImportItem] = Field(..., min_length=1)


class DishImportPayload(BaseModel):
    categories: list[DishImportCategory] = Field(..., min_length=1)
