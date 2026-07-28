from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_serializer

from optiflow_shared.responses import (
    error_response as shared_error_response,
    serialize_datetime_value,
    success_response as shared_success_response,
    utc_timestamp,
)


class AssignmentRequestResponse(BaseModel):
    request_id: str
    run_id: str | None
    incident_id: str
    specialist_id: str
    reservation_id: str | None
    message: str
    status: str
    idempotency_key: str | None
    created_at: datetime
    expires_at: datetime
    responded_at: datetime | None
    response_note: str | None
    response_reason: str | None
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @field_serializer("created_at", "expires_at", "responded_at", "updated_at")
    def serialize_datetime(self, value: datetime | None) -> str | None:
        return serialize_datetime_value(value)


class AssignmentRequestVerificationResponse(BaseModel):
    verified: bool
    result: str
    assignment_request_id: str
    expected_values: dict[str, str]
    actual_values: dict[str, Any] | None
    failed_checks: list[str]
    checked_at: datetime
    current_status: str | None

    @field_serializer("checked_at")
    def serialize_checked_at(self, value: datetime) -> str:
        return serialize_datetime_value(value) or ""


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


class ConfiguredResponseData(BaseModel):
    simulation_rule_id: int
    specialist_id: str | None
    incident_id: str | None
    status: str
    reason: str | None
    response_delay_seconds: int
    apply_once: bool
    active: bool
    created_at: str
    expires_at: str | None
    consumed_at: str | None


class FailureModeData(BaseModel):
    simulation_rule_id: int
    enabled: bool
    failure_type: str
    status_code: int
    delay_seconds: int
    affected_endpoint: str | None
    scope: str | None
    apply_once: bool
    remaining_uses: int | None
    message: str | None
    created_at: str
    expires_at: str | None


class FailureModeStateData(BaseModel):
    enabled: bool
    active_rules: list[FailureModeData]


class SimulationStateData(BaseModel):
    queued_specialist_responses: list[ConfiguredResponseData]
    active_failure_modes: list[FailureModeData]
    pending_assignment_requests: list[AssignmentRequestResponse]
    last_reset_at: str | None
    demo_seed_status: str


def success_response(data: Any, message: str = "Request completed successfully") -> dict[str, Any]:
    return shared_success_response(data, message)


def error_response(message: str, error_code: str) -> dict[str, Any]:
    return shared_error_response(message, error_code)
