from typing import Annotated

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator


ReservationId = Annotated[str, Field(min_length=1, max_length=64)]
SpecialistId = Annotated[str, Field(min_length=1, max_length=64)]
IncidentId = Annotated[str, Field(min_length=1, max_length=64)]
Skill = Annotated[str, Field(min_length=1, max_length=80)]


def normalize_identifier(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} cannot be empty")
    return normalized.upper()


def normalize_specialist_id(value: str) -> str:
    return normalize_identifier(value, "specialist_id")


def normalize_reservation_id(value: str) -> str:
    return normalize_identifier(value, "reservation_id")


def normalize_incident_id(value: str) -> str:
    return normalize_identifier(value, "incident_id")


def normalize_skill(value: str) -> str:
    normalized = value.strip().lower()
    if not normalized:
        raise ValueError("skill cannot be empty")
    if len(normalized) > 80:
        raise ValueError("skill must be at most 80 characters")
    return normalized


def normalize_skills(values: list[str]) -> list[str]:
    if not values:
        raise ValueError("skills must contain at least one value")
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        skill = normalize_skill(value)
        if skill not in seen:
            normalized.append(skill)
            seen.add(skill)
    if len(normalized) > 25:
        raise ValueError("skills must contain at most 25 values")
    return normalized


def normalize_email(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip().lower()
    if not normalized:
        return None
    if len(normalized) > 254 or "@" not in normalized or normalized.startswith("@") or normalized.endswith("@"):
        raise ValueError("email must be a valid email address")
    return normalized


class ReservationCreateRequest(BaseModel):
    reservation_id: ReservationId
    specialist_id: SpecialistId
    incident_id: IncidentId
    expires_in_seconds: int | None = Field(default=None, ge=30, le=3600)

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    @field_validator("reservation_id")
    @classmethod
    def validate_reservation_id(cls, value: str) -> str:
        return normalize_reservation_id(value)

    @field_validator("specialist_id")
    @classmethod
    def validate_specialist_id(cls, value: str) -> str:
        return normalize_specialist_id(value)

    @field_validator("incident_id")
    @classmethod
    def validate_incident_id(cls, value: str) -> str:
        return normalize_incident_id(value)


class LegacyTentativeReservationRequest(BaseModel):
    specialistId: SpecialistId
    escalationId: IncidentId
    idempotencyKey: str | None = Field(default=None, max_length=128)

    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    @field_validator("specialistId")
    @classmethod
    def validate_specialist_id(cls, value: str) -> str:
        return normalize_specialist_id(value)

    @field_validator("escalationId")
    @classmethod
    def validate_incident_id(cls, value: str) -> str:
        return normalize_incident_id(value)


class AdminAvailabilityRequest(BaseModel):
    unavailable: bool = True

    model_config = ConfigDict(extra="forbid")


class AdminCapacityRequest(BaseModel):
    maximumConcurrentAssignments: int = Field(ge=1, le=100)

    model_config = ConfigDict(extra="forbid")


class AdminWorkloadRequest(BaseModel):
    current_workload: int | None = Field(
        default=None,
        ge=0,
        le=100,
        validation_alias=AliasChoices("current_workload", "activeAssignmentCount", "active_assignment_count"),
    )

    model_config = ConfigDict(extra="ignore")
