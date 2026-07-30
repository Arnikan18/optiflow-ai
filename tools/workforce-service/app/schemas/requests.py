from datetime import datetime, timezone
from typing import Annotated

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator


ReservationId = Annotated[str, Field(min_length=1, max_length=64)]
RunId = Annotated[str, Field(min_length=1, max_length=64)]
SpecialistId = Annotated[str, Field(min_length=1, max_length=64)]
IncidentId = Annotated[str, Field(min_length=1, max_length=64)]
Skill = Annotated[str, Field(min_length=1, max_length=80)]
CancellationReason = Annotated[str, Field(min_length=1, max_length=1000)]
IdempotencyKey = Annotated[str, Field(min_length=1, max_length=128)]


def normalize_identifier(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} cannot be empty")
    return normalized.upper()


def normalize_specialist_id(value: str) -> str:
    return normalize_identifier(value, "specialist_id")


def normalize_reservation_id(value: str) -> str:
    return normalize_identifier(value, "reservation_id")


def normalize_run_id(value: str) -> str:
    return normalize_identifier(value, "run_id")


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


def normalize_datetime(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("datetime values must include timezone information")
    return value.astimezone(timezone.utc)


class ReservationCreateRequest(BaseModel):
    reservation_id: ReservationId
    run_id: RunId | None = None
    specialist_id: SpecialistId
    incident_id: IncidentId
    idempotency_key: IdempotencyKey | None = None
    expires_in_seconds: int | None = Field(default=None, ge=30, le=3600)

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    @field_validator("reservation_id")
    @classmethod
    def validate_reservation_id(cls, value: str) -> str:
        return normalize_reservation_id(value)

    @field_validator("run_id")
    @classmethod
    def validate_run_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return normalize_run_id(value)

    @field_validator("specialist_id")
    @classmethod
    def validate_specialist_id(cls, value: str) -> str:
        return normalize_specialist_id(value)

    @field_validator("incident_id")
    @classmethod
    def validate_incident_id(cls, value: str) -> str:
        return normalize_incident_id(value)

    @field_validator("idempotency_key")
    @classmethod
    def validate_idempotency_key(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("idempotency_key cannot be empty")
        return normalized


class ReservationVerificationRequest(BaseModel):
    reservation_id: ReservationId
    expected_run_id: RunId
    expected_incident_id: IncidentId
    expected_specialist_id: SpecialistId
    expected_status: str = "CONFIRMED"

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, validate_default=True)

    @field_validator("reservation_id")
    @classmethod
    def validate_reservation_id(cls, value: str) -> str:
        return normalize_reservation_id(value)

    @field_validator("expected_run_id")
    @classmethod
    def validate_run_id(cls, value: str) -> str:
        return normalize_run_id(value)

    @field_validator("expected_incident_id")
    @classmethod
    def validate_incident_id(cls, value: str) -> str:
        return normalize_incident_id(value)

    @field_validator("expected_specialist_id")
    @classmethod
    def validate_specialist_id(cls, value: str) -> str:
        return normalize_specialist_id(value)

    @field_validator("expected_status")
    @classmethod
    def validate_expected_status(cls, value: str) -> str:
        normalized = value.strip().upper()
        if normalized != "CONFIRMED":
            raise ValueError("expected_status must be CONFIRMED")
        return normalized


class LegacyTentativeReservationRequest(BaseModel):
    specialistId: SpecialistId
    escalationId: IncidentId
    runId: RunId | None = None
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

    @field_validator("runId")
    @classmethod
    def validate_run_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return normalize_run_id(value)


class ReservationCancelRequest(BaseModel):
    cancellation_reason: CancellationReason | None = None

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

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


class SpecialistSimulationSeedRequest(BaseModel):
    specialist_id: SpecialistId
    name: str = Field(min_length=1, max_length=200)
    email: str | None = None
    skills: list[Skill]
    capacity: int = Field(ge=1, le=100)
    current_workload: int = Field(default=0, ge=0, le=100)
    availability: bool = True
    active: bool = True
    created_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    @field_validator("specialist_id")
    @classmethod
    def validate_specialist_id(cls, value: str) -> str:
        return normalize_specialist_id(value)

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("name cannot be empty")
        return normalized

    @field_validator("email")
    @classmethod
    def validate_email(cls, value: str | None) -> str | None:
        return normalize_email(value)

    @field_validator("skills")
    @classmethod
    def validate_skills(cls, values: list[str]) -> list[str]:
        return normalize_skills(values)

    @field_validator("created_at", "updated_at")
    @classmethod
    def validate_datetime_fields(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        return normalize_datetime(value)


class ReservationSimulationSeedRequest(BaseModel):
    reservation_id: ReservationId
    run_id: RunId | None = None
    specialist_id: SpecialistId
    incident_id: IncidentId
    status: str = "TENTATIVE"
    idempotency_key: IdempotencyKey | None = None
    created_at: datetime
    expires_at: datetime
    confirmed_at: datetime | None = None
    cancelled_at: datetime | None = None
    cancellation_reason: CancellationReason | None = None
    updated_at: datetime | None = None

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, validate_default=True)

    @field_validator("reservation_id")
    @classmethod
    def validate_reservation_id(cls, value: str) -> str:
        return normalize_reservation_id(value)

    @field_validator("run_id")
    @classmethod
    def validate_run_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return normalize_run_id(value)

    @field_validator("specialist_id")
    @classmethod
    def validate_specialist_id(cls, value: str) -> str:
        return normalize_specialist_id(value)

    @field_validator("incident_id")
    @classmethod
    def validate_incident_id(cls, value: str) -> str:
        return normalize_incident_id(value)

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        normalized = value.strip().upper()
        if normalized not in {"TENTATIVE", "CONFIRMED", "CANCELLED", "EXPIRED"}:
            raise ValueError("status must be one of: TENTATIVE, CONFIRMED, CANCELLED, EXPIRED")
        return normalized

    @field_validator("idempotency_key")
    @classmethod
    def validate_idempotency_key(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("idempotency_key cannot be empty")
        return normalized

    @field_validator("created_at", "expires_at", "confirmed_at", "cancelled_at", "updated_at")
    @classmethod
    def validate_datetime_fields(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        return normalize_datetime(value)


class WorkforceSimulationLoadStateRequest(BaseModel):
    scenario_id: str = Field(min_length=1, max_length=100)
    specialists: list[SpecialistSimulationSeedRequest]
    reservations: list[ReservationSimulationSeedRequest] = Field(default_factory=list)
    workloads: list[dict] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    @field_validator("scenario_id")
    @classmethod
    def validate_scenario_id(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("scenario_id cannot be empty")
        return normalized

    @field_validator("specialists")
    @classmethod
    def validate_unique_specialists(
        cls,
        values: list[SpecialistSimulationSeedRequest],
    ) -> list[SpecialistSimulationSeedRequest]:
        seen: set[str] = set()
        for specialist in values:
            if specialist.specialist_id in seen:
                raise ValueError("specialists cannot contain duplicate specialist_id values")
            if specialist.current_workload > specialist.capacity:
                raise ValueError("current_workload cannot exceed capacity")
            seen.add(specialist.specialist_id)
        return values

    @field_validator("reservations")
    @classmethod
    def validate_unique_reservations(
        cls,
        values: list[ReservationSimulationSeedRequest],
    ) -> list[ReservationSimulationSeedRequest]:
        seen: set[str] = set()
        for reservation in values:
            if reservation.reservation_id in seen:
                raise ValueError("reservations cannot contain duplicate reservation_id values")
            seen.add(reservation.reservation_id)
        return values


class WorkforceSimulationAvailabilityRequest(BaseModel):
    availability: bool
    reason: str | None = Field(default=None, max_length=1000)

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    @field_validator("reason")
    @classmethod
    def validate_reason(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class WorkforceSimulationReleaseRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=1000)

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    @field_validator("reason")
    @classmethod
    def validate_reason(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None
