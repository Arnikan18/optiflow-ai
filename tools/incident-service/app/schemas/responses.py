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
    return shared_success_response(data, message)


def error_response(message: str, error_code: str) -> dict[str, Any]:
    return shared_error_response(message, error_code)
