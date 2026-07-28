from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


SourceStatus = Literal["AVAILABLE", "UNAVAILABLE", "TIMEOUT", "INVALID_RESPONSE", "AUTH_FAILED"]
ComponentStatus = Literal["HEALTHY", "DEGRADED", "UNHEALTHY"]
FailureType = Literal["HTTP_ERROR", "TIMEOUT", "DELAY", "CONNECTION_FAILURE", "INVALID_RESPONSE"]
QueuedResponseStatus = Literal["ACCEPTED", "REJECTED"]


class SourceStatusData(BaseModel):
    source_name: str
    status: SourceStatus
    freshness_timestamp: str | None
    response_time_ms: float | None
    error_code: str | None = None
    error_message: str | None = None


class DemoCustomer(BaseModel):
    customer_id: str
    customer_name: str
    segment: str | None
    arr: float | None
    business_value: float | None
    renewal_date: str | None
    renewal_risk: bool | None
    strategic_priority: str | None
    current_incident_count: int = Field(ge=0)


class DemoIncident(BaseModel):
    incident_id: str
    customer_id: str
    title: str | None
    summary: str | None
    severity: str | None
    status: str | None
    sla_deadline: str | None
    sla_risk: bool | None
    required_skills: list[str]
    current_specialist_id: str | None
    assignment_status: str | None
    age_hours: float | None
    opened_at: str | None


class DemoSpecialist(BaseModel):
    specialist_id: str
    specialist_name: str
    skills: list[str]
    availability: bool | None
    capacity: int | None
    current_workload: int | None
    reserved_workload: int | None
    utilisation_percentage: float | None
    active_assignments: int | None


class DemoWorkload(BaseModel):
    specialist_id: str
    assigned_count: int | None
    tentative_reservation_count: int | None
    confirmed_reservation_count: int | None
    available_capacity: int | None
    utilisation_percentage: float | None


class PortfolioSummary(BaseModel):
    total_customers: int | None
    total_active_incidents: int | None
    total_at_risk_customers: int | None
    total_arr_represented: float | None
    total_arr_at_risk: float | None
    total_specialists: int | None
    available_specialists: int | None
    average_workload: float | None
    incidents_near_sla_breach: int | None
    unassigned_incidents: int | None
    generated_at: str
    partial: bool


class DemoPortfolioData(BaseModel):
    generated_at: str
    degraded: bool
    customers: list[DemoCustomer]
    incidents: list[DemoIncident]
    specialists: list[DemoSpecialist]
    workloads: list[DemoWorkload]
    portfolio_summary: PortfolioSummary
    sources: list[SourceStatusData]


class HealthComponent(BaseModel):
    name: str
    status: ComponentStatus
    latency_ms: float | None
    checked_at: str
    message: str | None = None


class DemoHealthData(BaseModel):
    overall_status: ComponentStatus
    checked_at: str
    components: list[HealthComponent]


class SpecialistResponseSimulationRequest(BaseModel):
    specialist_id: str | None = None
    incident_id: str | None = None
    status: QueuedResponseStatus
    reason: str | None = None
    response_delay_seconds: int = Field(default=0, ge=0, le=3600)
    apply_once: bool = True
    expires_after_seconds: int | None = Field(default=None, ge=1, le=86400)

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    @field_validator("specialist_id", "incident_id", "reason")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class FailureSimulationRequest(BaseModel):
    service: Literal["crm", "incident", "workforce", "communication"]
    enabled: bool = True
    failure_type: FailureType = "HTTP_ERROR"
    status_code: int = Field(default=503, ge=400, le=599)
    delay_seconds: int = Field(default=0, ge=0, le=60)
    affected_endpoint: str | None = None
    scope: str | None = None
    apply_once: bool = False
    expires_after_seconds: int | None = Field(default=None, ge=1, le=86400)
    message: str | None = Field(default=None, max_length=300)

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    @field_validator("affected_endpoint", "scope", "message")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class DemoResetRequest(BaseModel):
    services: list[Literal["crm", "incident", "workforce", "communication"]] | None = None

    model_config = ConfigDict(extra="forbid")


class SimulationStateData(BaseModel):
    communication: dict[str, Any] | None
    services: dict[str, Any]
    degraded: bool
    generated_at: str

