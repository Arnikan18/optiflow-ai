from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import CheckConstraint, DateTime, Index, Integer, PrimaryKeyConstraint, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database.base import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Incident(Base):
    __tablename__ = "incidents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    incident_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    customer_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(String(2000), nullable=False)
    priority: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True, default="OPEN")
    sla_deadline: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    estimated_effort_minutes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    assigned_specialist_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    assignment_run_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    assignment_idempotency_key: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    assigned_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )

    __table_args__ = (
        CheckConstraint(
            "priority IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')",
            name="ck_incidents_priority",
        ),
        CheckConstraint(
            "status IN ('OPEN', 'IN_PROGRESS', 'RESOLVED', 'CLOSED')",
            name="ck_incidents_status",
        ),
        CheckConstraint(
            "estimated_effort_minutes IS NULL OR estimated_effort_minutes > 0",
            name="ck_incidents_estimated_effort_positive",
        ),
        Index("ix_incidents_sla_status", "sla_deadline", "status"),
        Index("ix_incidents_assignment_run", "incident_id", "assignment_run_id"),
    )


class Escalation(Base):
    __tablename__ = "escalations"
    escalation_id: Mapped[str] = mapped_column(String, primary_key=True)
    customer_id: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    severity: Mapped[str] = mapped_column(String, nullable=False)
    priority: Mapped[str] = mapped_column(String, nullable=False)
    sla_deadline: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False)
    required_duration_minutes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    workaround_status: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    current_specialist_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[str] = mapped_column(String, nullable=False)
    updated_at: Mapped[str] = mapped_column(String, nullable=False)
    scenario_id: Mapped[str] = mapped_column(String, nullable=False)

class EscalationSkill(Base):
    __tablename__ = "escalation_skills"
    escalation_id: Mapped[str] = mapped_column(String, primary_key=True)
    skill_code: Mapped[str] = mapped_column(String, primary_key=True)
    
    __table_args__ = (
        PrimaryKeyConstraint("escalation_id", "skill_code"),
    )

class EscalationAccess(Base):
    __tablename__ = "escalation_access"
    escalation_id: Mapped[str] = mapped_column(String, primary_key=True)
    access_code: Mapped[str] = mapped_column(String, primary_key=True)

    __table_args__ = (
        PrimaryKeyConstraint("escalation_id", "access_code"),
    )

class AssignmentHistory(Base):
    __tablename__ = "assignment_history"
    history_id: Mapped[str] = mapped_column(String, primary_key=True)
    escalation_id: Mapped[str] = mapped_column(String, nullable=False)
    specialist_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    action: Mapped[str] = mapped_column(String, nullable=False)
    reason: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    occurred_at: Mapped[str] = mapped_column(String, nullable=False)
    idempotency_key: Mapped[Optional[str]] = mapped_column(String, unique=True, nullable=True)

class IncidentEvent(Base):
    __tablename__ = "incident_events"
    event_id: Mapped[str] = mapped_column(String, primary_key=True)
    escalation_id: Mapped[str] = mapped_column(String, nullable=False)
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    payload: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    occurred_at: Mapped[str] = mapped_column(String, nullable=False)
    sequence_number: Mapped[int] = mapped_column(Integer, nullable=False)

class FailureMode(Base):
    __tablename__ = "failure_modes"
    mode_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    mode: Mapped[str] = mapped_column(String, nullable=False)
    enabled: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    delay_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    remaining_failures: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    updated_at: Mapped[str] = mapped_column(String, nullable=False)
