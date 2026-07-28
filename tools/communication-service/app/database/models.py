from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class AssignmentRequest(Base):
    __tablename__ = "assignment_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    request_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    run_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    incident_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    specialist_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    reservation_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    message: Mapped[str] = mapped_column(String(2000), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    responded_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    response_note: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    response_reason: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )

    notifications: Mapped[list["Notification"]] = relationship(back_populates="assignment_request", lazy="selectin")

    __table_args__ = (
        CheckConstraint(
            "status IN ('PENDING', 'ACCEPTED', 'REJECTED', 'EXPIRED', 'FAILED', 'CANCELLED')",
            name="ck_assignment_requests_status",
        ),
        Index("ix_assignment_requests_status_expires", "status", "expires_at"),
    )


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    notification_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    recipient: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    channel: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    subject: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    message: Mapped[str] = mapped_column(String(2000), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, unique=True, index=True)
    related_request_id: Mapped[Optional[str]] = mapped_column(
        String(64),
        ForeignKey("assignment_requests.request_id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now, index=True)
    attempted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    delivered_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    failure_reason: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )

    assignment_request: Mapped[Optional[AssignmentRequest]] = relationship(back_populates="notifications")

    __table_args__ = (
        CheckConstraint("channel IN ('EMAIL', 'SMS', 'IN_APP', 'WEBHOOK')", name="ck_notifications_channel"),
        CheckConstraint("status IN ('PENDING', 'DELIVERED', 'FAILED')", name="ck_notifications_status"),
        CheckConstraint("attempt_count >= 0", name="ck_notifications_attempt_count_nonnegative"),
        Index("ix_notifications_status_channel", "status", "channel"),
    )


class ConfiguredResponse(Base):
    __tablename__ = "configured_responses"

    configuration_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    specialist_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    incident_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    next_status: Mapped[str] = mapped_column(String, nullable=False)
    response_reason: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    delay_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    delay_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    apply_once: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    active: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    consumed_at: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    updated_at: Mapped[str] = mapped_column(String, nullable=False)

class FailureMode(Base):
    __tablename__ = "failure_modes"

    mode_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    mode: Mapped[str] = mapped_column(String, nullable=False)
    failure_type: Mapped[str] = mapped_column(String, nullable=False, default="TIMEOUT")
    enabled: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status_code: Mapped[int] = mapped_column(Integer, nullable=False, default=503)
    delay_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    delay_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    affected_endpoint: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    scope: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    remaining_failures: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    updated_at: Mapped[str] = mapped_column(String, nullable=False)
