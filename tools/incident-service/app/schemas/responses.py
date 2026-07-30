from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_serializer

from optiflow_shared.responses import (
    error_response as shared_error_response,
    serialize_datetime_value,
    success_response as shared_success_response,
    utc_timestamp,
)


class IncidentResponse(BaseModel):
    incident_id: str
    customer_id: str
    title: str
    description: str
    priority: str
    status: str
    sla_deadline: datetime
    estimated_effort_minutes: int | None = None
    assigned_specialist_id: str | None
    assignment_run_id: str | None = None
    assignment_idempotency_key: str | None = None
    assigned_at: datetime | None = None
    resolved_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @field_serializer("sla_deadline", "assigned_at", "resolved_at", "created_at", "updated_at")
    def serialize_datetime(self, value: datetime | None) -> str | None:
        return serialize_datetime_value(value)


class IncidentListData(BaseModel):
    incidents: list[IncidentResponse]
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)
    total_items: int = Field(ge=0)
    total_pages: int = Field(ge=0)


class ResetResponseData(BaseModel):
    seeded_records: int


class IncidentAssignmentVerificationResponse(BaseModel):
    verified: bool
    result: str
    incident_id: str
    expected_values: dict[str, str]
    actual_values: dict[str, Any] | None
    failed_checks: list[str]
    checked_at: datetime
    assignment_status: str | None

    @field_serializer("checked_at")
    def serialize_checked_at(self, value: datetime) -> str:
        return serialize_datetime_value(value) or ""


def success_response(data: Any, message: str = "Request completed successfully") -> dict[str, Any]:
    return shared_success_response(data, message)


def error_response(message: str, error_code: str) -> dict[str, Any]:
    return shared_error_response(message, error_code)
