from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_serializer


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def serialize_datetime_value(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


class SpecialistResponse(BaseModel):
    specialist_id: str
    name: str
    email: str | None
    skills: list[str]
    capacity: int
    current_workload: int
    availability: bool
    active: bool
    effective_workload: int
    available_capacity: int
    operationally_available: bool
    created_at: datetime
    updated_at: datetime

    @field_serializer("created_at", "updated_at")
    def serialize_datetime(self, value: datetime) -> str:
        return serialize_datetime_value(value) or ""


class SpecialistListData(BaseModel):
    specialists: list[SpecialistResponse]
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)
    total_items: int = Field(ge=0)
    total_pages: int = Field(ge=0)


class ReservationResponse(BaseModel):
    reservation_id: str
    specialist_id: str
    incident_id: str
    status: str
    created_at: datetime
    expires_at: datetime
    confirmed_at: datetime | None
    cancelled_at: datetime | None
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @field_serializer("created_at", "expires_at", "confirmed_at", "cancelled_at", "updated_at")
    def serialize_datetime(self, value: datetime | None) -> str | None:
        return serialize_datetime_value(value)


class ResetResponseData(BaseModel):
    specialist_count: int
    reservation_count: int


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
