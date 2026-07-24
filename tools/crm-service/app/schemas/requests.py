from datetime import date
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator


SUPPORTED_TIERS = {
    "standard": "Standard",
    "premium": "Premium",
    "enterprise": "Enterprise",
}

CustomerId = Annotated[str, Field(min_length=1, max_length=64)]
CustomerName = Annotated[str, Field(min_length=1, max_length=200)]
Money = Annotated[Decimal, Field(ge=Decimal("0"), max_digits=14, decimal_places=2)]


def normalize_customer_id(value: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError("customer_id cannot be empty")
    return normalized.upper()


def normalize_tier(value: str) -> str:
    normalized = value.strip().lower()
    if not normalized:
        raise ValueError("tier cannot be empty")
    if normalized not in SUPPORTED_TIERS:
        supported = ", ".join(SUPPORTED_TIERS.values())
        raise ValueError(f"tier must be one of: {supported}")
    return SUPPORTED_TIERS[normalized]


def normalize_search(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


class CustomerCreateRequest(BaseModel):
    customer_id: CustomerId
    name: CustomerName
    tier: str
    arr: Money
    renewal_date: date
    active: bool = True

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    @field_validator("customer_id")
    @classmethod
    def validate_customer_id(cls, value: str) -> str:
        return normalize_customer_id(value)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("name cannot be empty")
        return normalized

    @field_validator("tier")
    @classmethod
    def validate_tier(cls, value: str) -> str:
        return normalize_tier(value)


class CustomerUpdateRequest(BaseModel):
    name: CustomerName
    tier: str
    arr: Money
    renewal_date: date
    active: bool

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("name cannot be empty")
        return normalized

    @field_validator("tier")
    @classmethod
    def validate_tier(cls, value: str) -> str:
        return normalize_tier(value)
