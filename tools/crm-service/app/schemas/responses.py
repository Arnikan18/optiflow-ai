from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_serializer

from optiflow_shared.responses import (
    error_response as shared_error_response,
    serialize_datetime_value,
    success_response as shared_success_response,
    utc_timestamp,
)


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
        return serialize_datetime_value(value) or ""


class CustomerListData(BaseModel):
    customers: list[CustomerResponse]
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)
    total_items: int = Field(ge=0)
    total_pages: int = Field(ge=0)


class ResetResponseData(BaseModel):
    seeded_records: int


def success_response(data: Any, message: str = "Request completed successfully") -> dict[str, Any]:
    return shared_success_response(data, message)


def error_response(message: str, error_code: str) -> dict[str, Any]:
    return shared_error_response(message, error_code)
