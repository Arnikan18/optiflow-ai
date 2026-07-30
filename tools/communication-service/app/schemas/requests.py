from datetime import datetime, timezone
from typing import Annotated

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator, model_validator


ASSIGNMENT_STATUSES = {"PENDING", "ACCEPTED", "REJECTED", "EXPIRED", "FAILED", "CANCELLED"}
ASSIGNMENT_RESPONSES = {"ACCEPTED", "REJECTED"}
FAILURE_TYPES = {"HTTP_ERROR", "TIMEOUT", "DELAY", "CONNECTION_FAILURE", "INVALID_RESPONSE"}
NOTIFICATION_CHANNELS = {"EMAIL", "SMS", "IN_APP", "WEBHOOK"}
NOTIFICATION_STATUSES = {"PENDING", "DELIVERED", "FAILED"}

RequestId = Annotated[str, Field(min_length=1, max_length=64)]
RunId = Annotated[str, Field(min_length=1, max_length=64)]
IncidentId = Annotated[str, Field(min_length=1, max_length=64)]
SpecialistId = Annotated[str, Field(min_length=1, max_length=64)]
ReservationId = Annotated[str, Field(min_length=1, max_length=64)]
NotificationId = Annotated[str, Field(min_length=1, max_length=64)]
Recipient = Annotated[str, Field(min_length=1, max_length=500)]
Message = Annotated[str, Field(min_length=1, max_length=2000)]
Subject = Annotated[str, Field(min_length=1, max_length=200)]
ResponseNote = Annotated[str, Field(min_length=1, max_length=1000)]
IdempotencyKey = Annotated[str, Field(min_length=1, max_length=128)]


def normalize_identifier(value: str, field_name: str) -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} cannot be empty")
    return normalized.upper()


def normalize_request_id(value: str) -> str:
    return normalize_identifier(value, "request_id")


def normalize_run_id(value: str) -> str:
    return normalize_identifier(value, "run_id")


def normalize_incident_id(value: str) -> str:
    return normalize_identifier(value, "incident_id")


def normalize_specialist_id(value: str) -> str:
    return normalize_identifier(value, "specialist_id")


def normalize_reservation_id(value: str) -> str:
    return normalize_identifier(value, "reservation_id")


def normalize_notification_id(value: str) -> str:
    return normalize_identifier(value, "notification_id")


def normalize_channel(value: str) -> str:
    normalized = value.strip().upper()
    if normalized not in NOTIFICATION_CHANNELS:
        supported = ", ".join(sorted(NOTIFICATION_CHANNELS))
        raise ValueError(f"channel must be one of: {supported}")
    return normalized


def normalize_assignment_status(value: str) -> str:
    normalized = value.strip().upper()
    if normalized not in ASSIGNMENT_STATUSES:
        supported = ", ".join(sorted(ASSIGNMENT_STATUSES))
        raise ValueError(f"status must be one of: {supported}")
    return normalized


def normalize_assignment_response(value: str) -> str:
    normalized = value.strip().upper()
    if normalized not in ASSIGNMENT_RESPONSES:
        supported = ", ".join(sorted(ASSIGNMENT_RESPONSES))
        raise ValueError(f"response must be one of: {supported}")
    return normalized


def normalize_notification_status(value: str) -> str:
    normalized = value.strip().upper()
    if normalized not in NOTIFICATION_STATUSES:
        supported = ", ".join(sorted(NOTIFICATION_STATUSES))
        raise ValueError(f"status must be one of: {supported}")
    return normalized


def normalize_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def normalize_message(value: str, field_name: str = "message") -> str:
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} cannot be empty")
    return normalized


def normalize_datetime(value: datetime | None, field_name: str) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must include timezone information")
    return value.astimezone(timezone.utc)


def normalize_search(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def validate_email(value: str) -> str:
    normalized = value.strip().lower()
    if not normalized or "@" not in normalized or normalized.startswith("@") or normalized.endswith("@"):
        raise ValueError("recipient must be a valid email address for EMAIL notifications")
    return normalized


def validate_sms(value: str) -> str:
    normalized = value.strip()
    digits = normalized[1:] if normalized.startswith("+") else normalized
    if not normalized.startswith("+") or not digits.isdigit() or len(digits) < 8 or len(digits) > 15:
        raise ValueError("recipient must use + followed by 8 to 15 digits for SMS notifications")
    return normalized


class AssignmentRequestCreateRequest(BaseModel):
    request_id: RequestId
    run_id: RunId | None = None
    incident_id: IncidentId
    specialist_id: SpecialistId
    reservation_id: ReservationId | None = None
    message: Message
    idempotency_key: IdempotencyKey | None = None
    expires_in_seconds: int | None = Field(default=None, ge=30, le=86400)

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    @field_validator("request_id")
    @classmethod
    def validate_request_id(cls, value: str) -> str:
        return normalize_request_id(value)

    @field_validator("run_id")
    @classmethod
    def validate_run_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return normalize_run_id(value)

    @field_validator("incident_id")
    @classmethod
    def validate_incident_id(cls, value: str) -> str:
        return normalize_incident_id(value)

    @field_validator("specialist_id")
    @classmethod
    def validate_specialist_id(cls, value: str) -> str:
        return normalize_specialist_id(value)

    @field_validator("reservation_id")
    @classmethod
    def validate_reservation_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return normalize_reservation_id(value)

    @field_validator("message")
    @classmethod
    def validate_message(cls, value: str) -> str:
        return normalize_message(value)

    @field_validator("idempotency_key")
    @classmethod
    def validate_idempotency_key(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("idempotency_key cannot be empty")
        return normalized


class AssignmentRequestVerificationRequest(BaseModel):
    assignment_request_id: RequestId
    expected_run_id: RunId
    expected_incident_id: IncidentId
    expected_specialist_id: SpecialistId
    expected_status: str = "ACCEPTED"

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, validate_default=True)

    @field_validator("assignment_request_id")
    @classmethod
    def validate_request_id(cls, value: str) -> str:
        return normalize_request_id(value)

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
        normalized = normalize_assignment_status(value)
        if normalized != "ACCEPTED":
            raise ValueError("expected_status must be ACCEPTED")
        return normalized


class AssignmentResponseRequest(BaseModel):
    response: str
    response_note: ResponseNote | None = Field(default=None, validation_alias=AliasChoices("response_note", "responseReason", "response_reason"))

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    @field_validator("response")
    @classmethod
    def validate_response(cls, value: str) -> str:
        return normalize_assignment_response(value)

    @field_validator("response_note")
    @classmethod
    def validate_response_note(cls, value: str | None) -> str | None:
        return normalize_optional_text(value)


class NotificationCreateRequest(BaseModel):
    notification_id: NotificationId
    recipient: Recipient
    channel: str
    subject: Subject | None = None
    message: Message
    related_request_id: RequestId | None = None
    idempotency_key: IdempotencyKey | None = None

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    @field_validator("notification_id")
    @classmethod
    def validate_notification_id(cls, value: str) -> str:
        return normalize_notification_id(value)

    @field_validator("channel")
    @classmethod
    def validate_channel(cls, value: str) -> str:
        return normalize_channel(value)

    @field_validator("subject")
    @classmethod
    def validate_subject(cls, value: str | None) -> str | None:
        return normalize_optional_text(value)

    @field_validator("message")
    @classmethod
    def validate_message(cls, value: str) -> str:
        return normalize_message(value)

    @field_validator("related_request_id")
    @classmethod
    def validate_related_request_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return normalize_request_id(value)

    @field_validator("idempotency_key")
    @classmethod
    def validate_idempotency_key(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("idempotency_key cannot be empty")
        return normalized

    @model_validator(mode="after")
    def validate_channel_specific_fields(self) -> "NotificationCreateRequest":
        if self.channel == "EMAIL":
            self.recipient = validate_email(self.recipient)
            if self.subject is None:
                raise ValueError("subject is required for EMAIL notifications")
        elif self.channel == "SMS":
            self.recipient = validate_sms(self.recipient)
        else:
            self.recipient = normalize_message(self.recipient, "recipient")
        return self


class LegacyAssignmentCreateRequest(BaseModel):
    specialistId: SpecialistId
    escalationId: IncidentId
    runId: RunId | None = None
    reservationId: ReservationId | None = None
    message: str | None = None
    requestedMinutes: int | None = Field(default=None, ge=1, le=1440)
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

    @field_validator("reservationId")
    @classmethod
    def validate_reservation_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return normalize_reservation_id(value)


class LegacyAssignmentResponseRequest(BaseModel):
    status: str = "ACCEPTED"
    reason: str | None = None

    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        return normalize_assignment_response(value)


class LegacyNotificationCreateRequest(BaseModel):
    recipientType: str = "SPECIALIST"
    recipientId: str
    notificationType: str = "IN_APP"
    message: Message
    idempotencyKey: str | None = Field(default=None, max_length=128)

    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    @field_validator("recipientId")
    @classmethod
    def validate_recipient_id(cls, value: str) -> str:
        return normalize_message(value, "recipientId")

    @field_validator("message")
    @classmethod
    def validate_message(cls, value: str) -> str:
        return normalize_message(value)


class AdminConfiguredResponseRequest(BaseModel):
    specialist_id: SpecialistId | None = Field(default=None, validation_alias=AliasChoices("specialist_id", "specialistId"))
    incident_id: IncidentId | None = Field(default=None, validation_alias=AliasChoices("incident_id", "incidentId", "escalationId"))
    status: str = "ACCEPTED"
    reason: str | None = None
    response_delay_seconds: int = Field(
        default=0,
        ge=0,
        le=3600,
        validation_alias=AliasChoices("response_delay_seconds", "responseDelaySeconds", "delaySeconds"),
    )
    delayMs: int | None = Field(default=None, ge=0, le=60000)
    apply_once: bool = Field(default=True, validation_alias=AliasChoices("apply_once", "applyOnce"))
    expires_after_seconds: int | None = Field(
        default=None,
        ge=1,
        le=86400,
        validation_alias=AliasChoices("expires_after_seconds", "expiresAfterSeconds"),
    )

    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    @field_validator("specialist_id")
    @classmethod
    def validate_specialist_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return normalize_specialist_id(value)

    @field_validator("incident_id")
    @classmethod
    def validate_incident_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return normalize_incident_id(value)

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        return normalize_assignment_response(value)


class AdminFailureModeRequest(BaseModel):
    enabled: bool = False
    failure_type: str = Field(default="HTTP_ERROR", validation_alias=AliasChoices("failure_type", "failureType", "mode"))
    status_code: int = Field(default=503, ge=400, le=599, validation_alias=AliasChoices("status_code", "statusCode"))
    delay_seconds: int = Field(default=0, ge=0, le=60, validation_alias=AliasChoices("delay_seconds", "delaySeconds"))
    affected_endpoint: str | None = Field(
        default=None,
        validation_alias=AliasChoices("affected_endpoint", "affectedEndpoint"),
    )
    scope: str | None = None
    apply_once: bool = Field(default=False, validation_alias=AliasChoices("apply_once", "applyOnce"))
    expires_after_seconds: int | None = Field(
        default=None,
        ge=1,
        le=86400,
        validation_alias=AliasChoices("expires_after_seconds", "expiresAfterSeconds"),
    )
    message: str | None = None

    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    @field_validator("failure_type")
    @classmethod
    def validate_failure_type(cls, value: str) -> str:
        normalized = value.strip().upper()
        if normalized not in FAILURE_TYPES:
            supported = ", ".join(sorted(FAILURE_TYPES))
            raise ValueError(f"failure_type must be one of: {supported}")
        return normalized

    @field_validator("affected_endpoint", "scope")
    @classmethod
    def validate_optional_text(cls, value: str | None) -> str | None:
        return normalize_optional_text(value)

    @field_validator("message")
    @classmethod
    def validate_message(cls, value: str | None) -> str | None:
        normalized = normalize_optional_text(value)
        if normalized and len(normalized) > 300:
            raise ValueError("message must be at most 300 characters")
        return normalized


class AssignmentRequestSimulationSeedRequest(BaseModel):
    request_id: RequestId
    run_id: RunId | None = None
    incident_id: IncidentId
    specialist_id: SpecialistId
    reservation_id: ReservationId | None = None
    message: Message
    status: str = "PENDING"
    idempotency_key: IdempotencyKey | None = None
    created_at: datetime
    expires_at: datetime
    responded_at: datetime | None = None
    response_note: ResponseNote | None = None
    response_reason: ResponseNote | None = None
    updated_at: datetime | None = None

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, validate_default=True)

    @field_validator("request_id")
    @classmethod
    def validate_request_id(cls, value: str) -> str:
        return normalize_request_id(value)

    @field_validator("run_id")
    @classmethod
    def validate_run_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return normalize_run_id(value)

    @field_validator("incident_id")
    @classmethod
    def validate_incident_id(cls, value: str) -> str:
        return normalize_incident_id(value)

    @field_validator("specialist_id")
    @classmethod
    def validate_specialist_id(cls, value: str) -> str:
        return normalize_specialist_id(value)

    @field_validator("reservation_id")
    @classmethod
    def validate_reservation_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return normalize_reservation_id(value)

    @field_validator("message")
    @classmethod
    def validate_message(cls, value: str) -> str:
        return normalize_message(value)

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        return normalize_assignment_status(value)

    @field_validator("idempotency_key")
    @classmethod
    def validate_idempotency_key(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("idempotency_key cannot be empty")
        return normalized

    @field_validator("created_at", "expires_at", "responded_at", "updated_at")
    @classmethod
    def validate_datetimes(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        return normalize_datetime(value, "datetime")

    @field_validator("response_note", "response_reason")
    @classmethod
    def validate_response_text(cls, value: str | None) -> str | None:
        return normalize_optional_text(value)


class NotificationSimulationSeedRequest(BaseModel):
    notification_id: NotificationId
    recipient: Recipient
    channel: str
    subject: Subject | None = None
    message: Message
    status: str = "DELIVERED"
    idempotency_key: IdempotencyKey | None = None
    related_request_id: RequestId | None = None
    created_at: datetime
    attempted_at: datetime | None = None
    delivered_at: datetime | None = None
    failure_reason: str | None = Field(default=None, max_length=300)
    attempt_count: int = Field(default=1, ge=0)
    updated_at: datetime | None = None

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True, validate_default=True)

    @field_validator("notification_id")
    @classmethod
    def validate_notification_id(cls, value: str) -> str:
        return normalize_notification_id(value)

    @field_validator("channel")
    @classmethod
    def validate_channel(cls, value: str) -> str:
        return normalize_channel(value)

    @field_validator("subject", "failure_reason")
    @classmethod
    def validate_optional_text(cls, value: str | None) -> str | None:
        return normalize_optional_text(value)

    @field_validator("message")
    @classmethod
    def validate_message(cls, value: str) -> str:
        return normalize_message(value)

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        return normalize_notification_status(value)

    @field_validator("idempotency_key")
    @classmethod
    def validate_idempotency_key(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("idempotency_key cannot be empty")
        return normalized

    @field_validator("related_request_id")
    @classmethod
    def validate_related_request_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return normalize_request_id(value)

    @field_validator("created_at", "attempted_at", "delivered_at", "updated_at")
    @classmethod
    def validate_datetimes(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        return normalize_datetime(value, "datetime")


class CommunicationSimulationLoadStateRequest(BaseModel):
    scenario_id: str = Field(min_length=1, max_length=100)
    assignment_requests: list[AssignmentRequestSimulationSeedRequest] = Field(default_factory=list)
    notifications: list[NotificationSimulationSeedRequest] = Field(default_factory=list)

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    @field_validator("scenario_id")
    @classmethod
    def validate_scenario_id(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("scenario_id cannot be empty")
        return normalized

    @field_validator("assignment_requests")
    @classmethod
    def validate_unique_assignments(
        cls,
        values: list[AssignmentRequestSimulationSeedRequest],
    ) -> list[AssignmentRequestSimulationSeedRequest]:
        seen: set[str] = set()
        for assignment in values:
            if assignment.request_id in seen:
                raise ValueError("assignment_requests cannot contain duplicate request_id values")
            seen.add(assignment.request_id)
        return values

    @field_validator("notifications")
    @classmethod
    def validate_unique_notifications(
        cls,
        values: list[NotificationSimulationSeedRequest],
    ) -> list[NotificationSimulationSeedRequest]:
        seen: set[str] = set()
        for notification in values:
            if notification.notification_id in seen:
                raise ValueError("notifications cannot contain duplicate notification_id values")
            seen.add(notification.notification_id)
        return values
