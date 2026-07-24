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


class AssignmentRequestResponse(BaseModel):
    request_id: str
    incident_id: str
    specialist_id: str
    message: str
    status: str
    created_at: datetime
    expires_at: datetime
    responded_at: datetime | None
    response_note: str | None
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @field_serializer("created_at", "expires_at", "responded_at", "updated_at")
    def serialize_datetime(self, value: datetime | None) -> str | None:
        return serialize_datetime_value(value)


class AssignmentRequestListData(BaseModel):
    assignment_requests: list[AssignmentRequestResponse]
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)
    total_items: int = Field(ge=0)
    total_pages: int = Field(ge=0)


class NotificationResponse(BaseModel):
    notification_id: str
    recipient: str
    channel: str
    subject: str | None
    message: str
    status: str
    idempotency_key: str | None
    related_request_id: str | None
    created_at: datetime
    attempted_at: datetime | None
    delivered_at: datetime | None
    failure_reason: str | None
    attempt_count: int
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @field_serializer("created_at", "attempted_at", "delivered_at", "updated_at")
    def serialize_datetime(self, value: datetime | None) -> str | None:
        return serialize_datetime_value(value)


class NotificationListData(BaseModel):
    notifications: list[NotificationResponse]
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)
    total_items: int = Field(ge=0)
    total_pages: int = Field(ge=0)


class ResetResponseData(BaseModel):
    assignment_request_count: int
    notification_count: int


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
