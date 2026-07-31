from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class SimulationError(Exception):
    def __init__(
        self,
        status_code: int,
        error_code: str,
        message: str,
        *,
        details: list[dict[str, Any]] | None = None,
    ) -> None:
        self.status_code = status_code
        self.error_code = error_code
        self.message = message
        self.details = details or []
        super().__init__(message)


class EnterpriseEventType(StrEnum):
    NEW_TICKET = "NEW_TICKET"
    RESOLVE_TICKET = "RESOLVE_TICKET"
    ESCALATE_PRIORITY = "ESCALATE_PRIORITY"
    CHANGE_SLA = "CHANGE_SLA"
    CHANGE_ESTIMATED_EFFORT = "CHANGE_ESTIMATED_EFFORT"
    CHANGE_WORKER_CAPACITY = "CHANGE_WORKER_CAPACITY"
    ENGINEER_ON_LEAVE = "ENGINEER_ON_LEAVE"
    ENGINEER_RETURNED = "ENGINEER_RETURNED"


class SimulationStatus(StrEnum):
    IDLE = "IDLE"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    STOPPED = "STOPPED"
    COMPLETED = "COMPLETED"
    ERROR = "ERROR"


class SimulationMode(StrEnum):
    TIMELINE = "TIMELINE"
    INTERACTIVE = "INTERACTIVE"


class EventProcessingStatus(StrEnum):
    RECEIVED = "RECEIVED"
    VALIDATED = "VALIDATED"
    APPLIED = "APPLIED"
    NOTIFIED = "NOTIFIED"
    FAILED = "FAILED"
    PARTIALLY_APPLIED = "PARTIALLY_APPLIED"


class NotificationStatus(StrEnum):
    NOT_REQUIRED = "NOT_REQUIRED"
    PENDING = "PENDING"
    DELIVERED = "DELIVERED"
    FAILED = "FAILED"
    ACKNOWLEDGED = "ACKNOWLEDGED"


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def normalize_identifier(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} cannot be empty")
    return normalized.upper()


def normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def normalize_datetime(value: datetime, field_name: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must include timezone information")
    return value.astimezone(timezone.utc)


class ScenarioMetadata(BaseModel):
    scenario_id: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=2000)
    version: str = Field(min_length=1, max_length=50)
    mode: SimulationMode
    duration: str = Field(min_length=1, max_length=100)
    start_time: datetime
    end_time: datetime
    timezone: str = Field(min_length=1, max_length=64)
    stages: list[str] = Field(min_length=1)
    tags: list[str] = Field(default_factory=list)
    schema_version: str = Field(default="1.0", min_length=1, max_length=20)
    created_at: datetime

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    @field_validator("scenario_id")
    @classmethod
    def validate_scenario_id(cls, value: str) -> str:
        return value.strip()

    @field_validator("start_time")
    @classmethod
    def validate_start_time(cls, value: datetime) -> datetime:
        return normalize_datetime(value, "start_time")

    @field_validator("end_time")
    @classmethod
    def validate_end_time(cls, value: datetime) -> datetime:
        return normalize_datetime(value, "end_time")

    @field_validator("created_at")
    @classmethod
    def validate_created_at(cls, value: datetime) -> datetime:
        return normalize_datetime(value, "created_at")

    @field_validator("stages")
    @classmethod
    def validate_stages(cls, values: list[str]) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()
        for value in values:
            stage = value.strip()
            if not stage:
                raise ValueError("stages cannot contain empty values")
            if stage in seen:
                raise ValueError("stages cannot contain duplicates")
            seen.add(stage)
            normalized.append(stage)
        return normalized

    @model_validator(mode="after")
    def validate_time_range(self) -> "ScenarioMetadata":
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        return self


class InitialState(BaseModel):
    scenario_id: str = Field(min_length=1, max_length=100)
    customers: list[dict[str, Any]] = Field(default_factory=list)
    specialists: list[dict[str, Any]] = Field(default_factory=list)
    incidents: list[dict[str, Any]] = Field(default_factory=list)
    assignments: list[dict[str, Any]] = Field(default_factory=list)
    reservations: list[dict[str, Any]] = Field(default_factory=list)
    notifications: list[dict[str, Any]] = Field(default_factory=list)
    workloads: list[dict[str, Any]] = Field(default_factory=list)
    sla_data: list[dict[str, Any]] = Field(default_factory=list)
    supporting_data: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    @field_validator("scenario_id")
    @classmethod
    def validate_scenario_id(cls, value: str) -> str:
        return value.strip()


class TimelineEvent(BaseModel):
    event_id: str = Field(min_length=1, max_length=100)
    scenario_id: str = Field(min_length=1, max_length=100)
    scheduled_time: datetime
    stage: str = Field(min_length=1, max_length=100)
    event_type: EnterpriseEventType
    payload: dict[str, Any]
    description: str = Field(min_length=1, max_length=1000)
    sequence: int = Field(ge=1)
    enabled: bool = True

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    @field_validator("event_id")
    @classmethod
    def validate_event_id(cls, value: str) -> str:
        return value.strip()

    @field_validator("scenario_id")
    @classmethod
    def validate_scenario_id(cls, value: str) -> str:
        return value.strip()

    @field_validator("scheduled_time")
    @classmethod
    def validate_scheduled_time(cls, value: datetime) -> datetime:
        return normalize_datetime(value, "scheduled_time")

    @field_validator("stage")
    @classmethod
    def validate_stage(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("stage cannot be empty")
        return normalized


class ScenarioBundle(BaseModel):
    metadata: ScenarioMetadata
    initial_state: InitialState
    timeline: list[TimelineEvent]
    folder_name: str

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    @model_validator(mode="after")
    def validate_consistency(self) -> "ScenarioBundle":
        scenario_id = self.metadata.scenario_id
        if self.initial_state.scenario_id != scenario_id:
            raise ValueError("initial_state scenario_id must match metadata scenario_id")

        seen_events: set[str] = set()
        last_time: datetime | None = None
        last_sequence = 0
        for event in self.timeline:
            if event.scenario_id != scenario_id:
                raise ValueError(f"timeline event {event.event_id} scenario_id does not match metadata")
            if event.event_id in seen_events:
                raise ValueError(f"duplicate event_id {event.event_id}")
            if event.stage not in self.metadata.stages:
                raise ValueError(f"timeline event {event.event_id} uses unsupported stage {event.stage}")
            if event.scheduled_time < self.metadata.start_time or event.scheduled_time > self.metadata.end_time:
                raise ValueError(f"timeline event {event.event_id} scheduled_time is outside scenario duration")
            if last_time is not None and event.scheduled_time < last_time:
                raise ValueError("timeline events must be ordered by scheduled_time")
            if event.sequence <= last_sequence:
                raise ValueError("timeline event sequence values must be strictly increasing")
            seen_events.add(event.event_id)
            last_time = event.scheduled_time
            last_sequence = event.sequence
        return self


class NewTicketPayload(BaseModel):
    incident_id: str = Field(min_length=1, max_length=64)
    customer_id: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=2000)
    priority: str = Field(min_length=1, max_length=16)
    sla_deadline: datetime
    estimated_effort_minutes: int | None = Field(default=None, ge=1, le=10080)
    required_skills: list[str] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    @field_validator("incident_id")
    @classmethod
    def validate_incident_id(cls, value: str) -> str:
        return normalize_identifier(value, "incident_id")

    @field_validator("customer_id")
    @classmethod
    def validate_customer_id(cls, value: str) -> str:
        return normalize_identifier(value, "customer_id")

    @field_validator("priority")
    @classmethod
    def validate_priority(cls, value: str) -> str:
        normalized = value.strip().upper()
        if normalized not in {"LOW", "MEDIUM", "HIGH", "CRITICAL"}:
            raise ValueError("priority must be one of: LOW, MEDIUM, HIGH, CRITICAL")
        return normalized

    @field_validator("sla_deadline")
    @classmethod
    def validate_sla_deadline(cls, value: datetime) -> datetime:
        return normalize_datetime(value, "sla_deadline")


class ResolveTicketPayload(BaseModel):
    incident_id: str = Field(min_length=1, max_length=64)
    resolved_at: datetime | None = None
    resolution_note: str | None = Field(default=None, max_length=1000)

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    @field_validator("incident_id")
    @classmethod
    def validate_incident_id(cls, value: str) -> str:
        return normalize_identifier(value, "incident_id")

    @field_validator("resolved_at")
    @classmethod
    def validate_resolved_at(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        return normalize_datetime(value, "resolved_at")

    @field_validator("resolution_note")
    @classmethod
    def validate_resolution_note(cls, value: str | None) -> str | None:
        return normalize_optional_text(value)


class EscalatePriorityPayload(BaseModel):
    incident_id: str = Field(min_length=1, max_length=64)
    new_priority: str = Field(min_length=1, max_length=16)

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    @field_validator("incident_id")
    @classmethod
    def validate_incident_id(cls, value: str) -> str:
        return normalize_identifier(value, "incident_id")

    @field_validator("new_priority")
    @classmethod
    def validate_new_priority(cls, value: str) -> str:
        normalized = value.strip().upper()
        if normalized not in {"LOW", "MEDIUM", "HIGH", "CRITICAL"}:
            raise ValueError("new_priority must be one of: LOW, MEDIUM, HIGH, CRITICAL")
        return normalized


class ChangeSLAPayload(BaseModel):
    incident_id: str = Field(min_length=1, max_length=64)
    sla_deadline: datetime

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    @field_validator("incident_id")
    @classmethod
    def validate_incident_id(cls, value: str) -> str:
        return normalize_identifier(value, "incident_id")

    @field_validator("sla_deadline")
    @classmethod
    def validate_sla_deadline(cls, value: datetime) -> datetime:
        return normalize_datetime(value, "sla_deadline")


class ChangeEstimatedEffortPayload(BaseModel):
    incident_id: str = Field(min_length=1, max_length=64)
    estimated_effort_minutes: int = Field(ge=1, le=10080)

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    @field_validator("incident_id")
    @classmethod
    def validate_incident_id(cls, value: str) -> str:
        return normalize_identifier(value, "incident_id")


class EngineerAvailabilityPayload(BaseModel):
    specialist_id: str = Field(min_length=1, max_length=64)
    reason: str | None = Field(default=None, max_length=1000)
    effective_at: datetime | None = None

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    @field_validator("specialist_id")
    @classmethod
    def validate_specialist_id(cls, value: str) -> str:
        return normalize_identifier(value, "specialist_id")

    @field_validator("reason")
    @classmethod
    def validate_reason(cls, value: str | None) -> str | None:
        return normalize_optional_text(value)

    @field_validator("effective_at")
    @classmethod
    def validate_effective_at(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        return normalize_datetime(value, "effective_at")


class ChangeWorkerCapacityPayload(BaseModel):
    specialist_id: str = Field(min_length=1, max_length=64)
    capacity: int | None = Field(default=None, ge=1, le=100)
    current_workload: int | None = Field(default=None, ge=0, le=100)
    reason: str | None = Field(default=None, max_length=1000)

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    @field_validator("specialist_id")
    @classmethod
    def validate_specialist_id(cls, value: str) -> str:
        return normalize_identifier(value, "specialist_id")

    @field_validator("reason")
    @classmethod
    def validate_reason(cls, value: str | None) -> str | None:
        return normalize_optional_text(value)

    @model_validator(mode="after")
    def validate_change(self) -> "ChangeWorkerCapacityPayload":
        if self.capacity is None and self.current_workload is None:
            raise ValueError("capacity or current_workload is required")
        if (
            self.capacity is not None
            and self.current_workload is not None
            and self.current_workload > self.capacity
        ):
            raise ValueError("current_workload cannot exceed capacity")
        return self


EVENT_PAYLOAD_MODELS: dict[EnterpriseEventType, type[BaseModel]] = {
    EnterpriseEventType.NEW_TICKET: NewTicketPayload,
    EnterpriseEventType.RESOLVE_TICKET: ResolveTicketPayload,
    EnterpriseEventType.ESCALATE_PRIORITY: EscalatePriorityPayload,
    EnterpriseEventType.CHANGE_SLA: ChangeSLAPayload,
    EnterpriseEventType.CHANGE_ESTIMATED_EFFORT: ChangeEstimatedEffortPayload,
    EnterpriseEventType.CHANGE_WORKER_CAPACITY: ChangeWorkerCapacityPayload,
    EnterpriseEventType.ENGINEER_ON_LEAVE: EngineerAvailabilityPayload,
    EnterpriseEventType.ENGINEER_RETURNED: EngineerAvailabilityPayload,
}


class JudgeEventRequest(BaseModel):
    event_type: EnterpriseEventType
    payload: dict[str, Any]
    event_id: str | None = Field(default=None, max_length=100)
    scenario_id: str | None = Field(default=None, max_length=100)
    description: str | None = Field(default=None, max_length=1000)
    effective_time: datetime | None = None
    idempotency_key: str | None = Field(default=None, max_length=128)

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    @field_validator("event_id", "scenario_id", "description", "idempotency_key")
    @classmethod
    def validate_optional_text(cls, value: str | None) -> str | None:
        return normalize_optional_text(value)

    @field_validator("effective_time")
    @classmethod
    def validate_effective_time(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        return normalize_datetime(value, "effective_time")

    def resolved_event_id(self) -> str:
        return self.event_id or f"JUDGE-{uuid4().hex[:12].upper()}"


class StartSimulationRequest(BaseModel):
    scenario_id: str | None = Field(default=None, max_length=100)
    mode: SimulationMode = SimulationMode.TIMELINE
    reset_existing: bool = False
    auto_advance: bool | None = None

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    @field_validator("scenario_id")
    @classmethod
    def validate_scenario_id(cls, value: str | None) -> str | None:
        return normalize_optional_text(value)


class SimulationEventResult(BaseModel):
    accepted: bool
    event_id: str
    event_type: EnterpriseEventType
    processing_status: EventProcessingStatus
    enterprise_changed: bool
    applied_at: datetime | None = None
    notification_status: NotificationStatus
    notification_id: str | None = None
    changed_entities: list[dict[str, Any]] = Field(default_factory=list)
    errors: list[dict[str, Any]] = Field(default_factory=list)


class SimulationStatusData(BaseModel):
    simulation_id: str | None
    scenario_id: str | None
    scenario_name: str | None
    mode: SimulationMode | None
    status: SimulationStatus
    current_time: datetime | None
    current_stage: str | None
    current_timeline_position: int
    processed_events: list[str]
    pending_events: list[str]
    last_event: dict[str, Any] | None
    enterprise_changed: bool
    notification_status: NotificationStatus
    started_at: datetime | None
    paused_at: datetime | None
    completed_at: datetime | None
    updated_at: datetime | None


class StartSimulationData(SimulationStatusData):
    next_event: dict[str, Any] | None


class AdvanceSimulationData(SimulationStatusData):
    processed_event: dict[str, Any] | None
    next_event: dict[str, Any] | None
    completed: bool


class ScenarioListData(BaseModel):
    scenarios: list[ScenarioMetadata]
    default_scenario_id: str | None


class EventHistoryData(BaseModel):
    events: list[dict[str, Any]]
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)
    total_items: int = Field(ge=0)
    total_pages: int = Field(ge=0)


class NotificationListData(BaseModel):
    notifications: list[dict[str, Any]]
    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)
    total_items: int = Field(ge=0)
    total_pages: int = Field(ge=0)
