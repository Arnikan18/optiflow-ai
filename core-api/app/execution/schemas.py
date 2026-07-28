from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field, field_serializer, field_validator


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def serialize_utc(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def normalize_identifier(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} cannot be empty")
    return normalized.upper()


class ExecutionVerificationRequest(BaseModel):
    reservation_id: str = Field(min_length=1, max_length=64)
    incident_id: str = Field(min_length=1, max_length=64)
    specialist_id: str = Field(min_length=1, max_length=64)
    assignment_request_id: str = Field(min_length=1, max_length=64)
    plan_id: str | None = Field(default=None, max_length=100)
    profile_name: str | None = Field(default=None, max_length=100)

    @field_validator("reservation_id", "incident_id", "specialist_id", "assignment_request_id")
    @classmethod
    def normalize_ids(cls, value: str, info) -> str:
        return normalize_identifier(value, info.field_name)

    @field_validator("plan_id", "profile_name")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class ComponentVerification(BaseModel):
    verified: bool
    result: str
    reservation_id: str | None = None
    incident_id: str | None = None
    assignment_request_id: str | None = None
    failed_checks: list[str] = Field(default_factory=list)
    current_status: str | None = None
    assignment_status: str | None = None
    expected_values: dict[str, Any] | None = None
    actual_values: dict[str, Any] | None = None
    checked_at: str | None = None
    source_unavailable: bool = False
    error: dict[str, Any] | None = None


class ExecutionReceipt(BaseModel):
    run_id: str
    plan_id: str | None
    profile_name: str | None
    reservation_id: str
    assignment_request_id: str
    incident_id: str
    specialist_id: str
    reservation_status: str | None
    communication_status: str | None
    assignment_status: str | None
    overall_verified: bool
    verification_timestamp: datetime
    failed_checks: list[str]
    final_execution_state: str

    @field_serializer("verification_timestamp")
    def serialize_verification_timestamp(self, value: datetime) -> str:
        return serialize_utc(value) or ""


class ExecutionVerificationResponse(BaseModel):
    run_id: str
    overall_verified: bool
    workforce_verification: ComponentVerification
    incident_verification: ComponentVerification
    communication_verification: ComponentVerification
    failed_components: list[str]
    checked_at: datetime
    recommended_next_state: Literal["COMPLETED", "WAITING", "COMPENSATE", "REPLAN", "FAILED"]
    execution_receipt: ExecutionReceipt

    @field_serializer("checked_at")
    def serialize_checked_at(self, value: datetime) -> str:
        return serialize_utc(value) or ""
