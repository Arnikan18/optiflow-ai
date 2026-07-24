from datetime import datetime, timezone
from typing import Annotated

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator, model_validator


ASSIGNMENT_STATUSES = {"PENDING", "ACCEPTED", "REJECTED", "EXPIRED", "CANCELLED"}
ASSIGNMENT_RESPONSES = {"ACCEPTED", "REJECTED"}
NOTIFICATION_CHANNELS = {"EMAIL", "SMS", "IN_APP", "WEBHOOK"}
NOTIFICATION_STATUSES = {"PENDING", "DELIVERED", "FAILED"}

RequestId = Annotated[str, Field(min_length=1, max_length=64)]
IncidentId = Annotated[str, Field(min_length=1, max_length=64)]
SpecialistId = Annotated[str, Field(min_length=1, max_length=64)]
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


def normalize_incident_id(value: str) -> str:
    return normalize_identifier(value, "incident_id")


def normalize_specialist_id(value: str) -> str:
    return normalize_identifier(value, "specialist_id")


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
    incident_id: IncidentId
    specialist_id: SpecialistId
    message: Message
    expires_in_seconds: int | None = Field(default=None, ge=30, le=86400)

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    @field_validator("request_id")
    @classmethod
    def validate_request_id(cls, value: str) -> str:
        return normalize_request_id(value)

    @field_validator("incident_id")
    @classmethod
    def validate_incident_id(cls, value: str) -> str:
        return normalize_incident_id(value)

    @field_validator("specialist_id")
    @classmethod
    def validate_specialist_id(cls, value: str) -> str:
        return normalize_specialist_id(value)

    @field_validator("message")
    @classmethod
    def validate_message(cls, value: str) -> str:
        return normalize_message(value)


class AssignmentResponseRequest(BaseModel):
    response: str
    response_note: ResponseNote | None = None

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
    specialistId: SpecialistId | None = None
    status: str = "ACCEPTED"
    reason: str | None = None
    delayMs: int = Field(default=0, ge=0, le=60000)

    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    @field_validator("specialistId")
    @classmethod
    def validate_specialist_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return normalize_specialist_id(value)

    @field_validator("status")
    @classmethod
    def validate_status(cls, value: str) -> str:
        return normalize_assignment_response(value)
