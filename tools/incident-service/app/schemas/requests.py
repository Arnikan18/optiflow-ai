from datetime import datetime, timezone
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator


SUPPORTED_PRIORITIES = {
    "low": "LOW",
    "medium": "MEDIUM",
    "high": "HIGH",
    "critical": "CRITICAL",
}

SUPPORTED_STATUSES = {
    "open": "OPEN",
    "in_progress": "IN_PROGRESS",
    "in-progress": "IN_PROGRESS",
    "in progress": "IN_PROGRESS",
    "resolved": "RESOLVED",
    "closed": "CLOSED",
}

IncidentId = Annotated[str, Field(min_length=1, max_length=64)]
CustomerId = Annotated[str, Field(min_length=1, max_length=64)]
SpecialistId = Annotated[str, Field(min_length=1, max_length=64)]
IncidentTitle = Annotated[str, Field(min_length=1, max_length=200)]
IncidentDescription = Annotated[str, Field(min_length=1, max_length=2000)]


def normalize_identifier(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} cannot be empty")
    return normalized.upper()


def normalize_incident_id(value: str) -> str:
    return normalize_identifier(value, "incident_id")


def normalize_customer_id(value: str) -> str:
    return normalize_identifier(value, "customer_id")


def normalize_specialist_id(value: str) -> str:
    return normalize_identifier(value, "specialist_id")


def normalize_priority(value: str) -> str:
    normalized = value.strip().lower()
    if not normalized:
        raise ValueError("priority cannot be empty")
    if normalized not in SUPPORTED_PRIORITIES:
        supported = ", ".join(SUPPORTED_PRIORITIES.values())
        raise ValueError(f"priority must be one of: {supported}")
    return SUPPORTED_PRIORITIES[normalized]


def normalize_status(value: str) -> str:
    normalized = value.strip().lower()
    if not normalized:
        raise ValueError("status cannot be empty")
    if normalized not in SUPPORTED_STATUSES:
        supported = ", ".join(("OPEN", "IN_PROGRESS", "RESOLVED", "CLOSED"))
        raise ValueError(f"status must be one of: {supported}")
    return SUPPORTED_STATUSES[normalized]


def normalize_datetime(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("sla_deadline must include timezone information")
    return value.astimezone(timezone.utc)


def normalize_search(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


class IncidentCreateRequest(BaseModel):
    incident_id: IncidentId
    customer_id: CustomerId
    title: IncidentTitle
    description: IncidentDescription
    priority: str
    sla_deadline: datetime
    status: str = "OPEN"
    assigned_specialist_id: SpecialistId | None = None

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, validate_default=True)

    @field_validator("incident_id")
    @classmethod
    def validate_incident_id(cls, value: str) -> str:
        return normalize_incident_id(value)

    @field_validator("customer_id")
    @classmethod
    def validate_customer_id(cls, value: str) -> str:
        return normalize_customer_id(value)

    @field_validator("title")
    @classmethod
    def validate_title(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("title cannot be empty")
        return normalized

    @field_validator("description")
    @classmethod
    def validate_description(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("description cannot be empty")
        return normalized

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, value: str) -> str:
        return normalize_priority(value)

    @field_validator("sla_deadline")
    @classmethod
    def validate_sla_deadline(cls, value: datetime) -> datetime:
        return normalize_datetime(value)

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        status = normalize_status(value)
        if status != "OPEN":
            raise ValueError("new incidents must start as OPEN")
        return status

    @field_validator("assigned_specialist_id")
    @classmethod
    def validate_assigned_specialist_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return normalize_specialist_id(value)


class IncidentStatusUpdateRequest(BaseModel):
    status: str

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        return normalize_status(value)


class IncidentAssignmentRequest(BaseModel):
    specialist_id: SpecialistId

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    @field_validator("specialist_id")
    @classmethod
    def validate_specialist_id(cls, value: str) -> str:
        return normalize_specialist_id(value)
