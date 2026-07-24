from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_serializer


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def serialize_datetime_value(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


class IncidentResponse(BaseModel):
    incident_id: str
    customer_id: str
    title: str
    description: str
    priority: str
    status: str
    sla_deadline: datetime
    assigned_specialist_id: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @field_serializer("sla_deadline", "created_at", "updated_at")
    def serialize_datetime(self, value: datetime) -> str:
        return serialize_datetime_value(value)


class IncidentListData(BaseModel):
    incidents: list[IncidentResponse]
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
