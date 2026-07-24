from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_serializer


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _serialize_datetime(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


class CustomerResponse(BaseModel):
    customer_id: str
    name: str
    tier: str
    arr: Decimal
    renewal_date: date
    active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @field_serializer("arr")
    def serialize_arr(self, value: Decimal) -> str:
        return format(value, "f")

    @field_serializer("created_at", "updated_at")
    def serialize_datetime(self, value: datetime) -> str:
        return _serialize_datetime(value)


class CustomerListData(BaseModel):
    customers: list[CustomerResponse]
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)
    total_items: int = Field(ge=0)
    total_pages: int = Field(ge=0)


class ResetResponseData(BaseModel):
    seeded_records: int


def success_response(data: Any, message: str = "Request completed successfully") -> dict[str, Any]:
    return {
        "success": True,
        "message": message,
        "timestamp": utc_timestamp(),
        "data": data,
    }


def error_response(message: str, error_code: str) -> dict[str, Any]:
    return {
        "success": False,
        "message": message,
        "errorCode": error_code,
        "timestamp": utc_timestamp(),
    }
