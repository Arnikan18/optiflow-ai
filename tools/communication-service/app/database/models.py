from typing import Optional
from sqlalchemy import String, Integer
from sqlalchemy.orm import Mapped, mapped_column
from app.database.base import Base

class AssignmentRequest(Base):
    __tablename__ = "assignment_requests"
    request_id: Mapped[str] = mapped_column(String, primary_key=True)
    specialist_id: Mapped[str] = mapped_column(String, nullable=False)
    escalation_id: Mapped[str] = mapped_column(String, nullable=False)
    requested_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    response_reason: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    idempotency_key: Mapped[Optional[str]] = mapped_column(String, unique=True, nullable=True)
    created_at: Mapped[str] = mapped_column(String, nullable=False)
    responded_at: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    scenario_id: Mapped[str] = mapped_column(String, nullable=False)

class Notification(Base):
    __tablename__ = "notifications"
    notification_id: Mapped[str] = mapped_column(String, primary_key=True)
    recipient_type: Mapped[str] = mapped_column(String, nullable=False)
    recipient_id: Mapped[str] = mapped_column(String, nullable=False)
    notification_type: Mapped[str] = mapped_column(String, nullable=False)
    message: Mapped[str] = mapped_column(String, nullable=False)
    delivery_status: Mapped[str] = mapped_column(String, nullable=False)
    idempotency_key: Mapped[Optional[str]] = mapped_column(String, unique=True, nullable=True)
    created_at: Mapped[str] = mapped_column(String, nullable=False)
    delivered_at: Mapped[Optional[str]] = mapped_column(String, nullable=True)

class ConfiguredResponse(Base):
    __tablename__ = "configured_responses"
    configuration_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    specialist_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    next_status: Mapped[str] = mapped_column(String, nullable=False)
    response_reason: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    delay_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    active: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    updated_at: Mapped[str] = mapped_column(String, nullable=False)

class FailureMode(Base):
    __tablename__ = "failure_modes"
    mode_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    mode: Mapped[str] = mapped_column(String, nullable=False)
    enabled: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    delay_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    remaining_failures: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    updated_at: Mapped[str] = mapped_column(String, nullable=False)
