from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_serializer

from optiflow_shared.responses import (
    error_response as shared_error_response,
    serialize_datetime_value,
    success_response as shared_success_response,
    utc_timestamp,
)


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


class WorkloadResponse(BaseModel):
    specialist_id: str
    assigned_count: int = Field(ge=0)
    tentative_reservation_count: int = Field(ge=0)
    confirmed_reservation_count: int = Field(ge=0)
    available_capacity: int = Field(ge=0)
    utilisation_percentage: float = Field(ge=0)
    updated_at: datetime

    @field_serializer("updated_at")
    def serialize_datetime(self, value: datetime) -> str:
        return serialize_datetime_value(value) or ""


class WorkloadListData(BaseModel):
    workloads: list[WorkloadResponse]
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)
    total_items: int = Field(ge=0)
    total_pages: int = Field(ge=0)


class ReservationResponse(BaseModel):
    reservation_id: str
    run_id: str | None
    specialist_id: str
    incident_id: str
    status: str
    idempotency_key: str | None
    created_at: datetime
    expires_at: datetime
    confirmed_at: datetime | None
    cancelled_at: datetime | None
    cancellation_reason: str | None
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @field_serializer("created_at", "expires_at", "confirmed_at", "cancelled_at", "updated_at")
    def serialize_datetime(self, value: datetime | None) -> str | None:
        return serialize_datetime_value(value)


class ReservationVerificationResponse(BaseModel):
    verified: bool
    result: str
    reservation_id: str
    expected_values: dict[str, str]
    actual_values: dict[str, Any] | None
    failed_checks: list[str]
    checked_at: datetime
    current_status: str | None

    @field_serializer("checked_at")
    def serialize_checked_at(self, value: datetime) -> str:
        return serialize_datetime_value(value) or ""


class ResetResponseData(BaseModel):
    specialist_count: int
    reservation_count: int


def success_response(data: Any, message: str = "Request completed successfully") -> dict[str, Any]:
    return shared_success_response(data, message)


def error_response(message: str, error_code: str) -> dict[str, Any]:
    return shared_error_response(message, error_code)
