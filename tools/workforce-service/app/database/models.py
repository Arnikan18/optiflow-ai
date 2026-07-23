from typing import Optional
from sqlalchemy import String, Integer, PrimaryKeyConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.database.base import Base

class Specialist(Base):
    __tablename__ = "specialists"
    specialist_id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    active: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    max_concurrent_assignments: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    daily_capacity_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    protected_emergency_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[str] = mapped_column(String, nullable=False)
    updated_at: Mapped[str] = mapped_column(String, nullable=False)
    scenario_id: Mapped[str] = mapped_column(String, nullable=False)

class SpecialistSkill(Base):
    __tablename__ = "specialist_skills"
    specialist_id: Mapped[str] = mapped_column(String, primary_key=True)
    skill_code: Mapped[str] = mapped_column(String, primary_key=True)
    proficiency_level: Mapped[int] = mapped_column(Integer, nullable=False)

    __table_args__ = (
        PrimaryKeyConstraint("specialist_id", "skill_code"),
    )

class SpecialistAccess(Base):
    __tablename__ = "specialist_access"
    specialist_id: Mapped[str] = mapped_column(String, primary_key=True)
    access_code: Mapped[str] = mapped_column(String, primary_key=True)

    __table_args__ = (
        PrimaryKeyConstraint("specialist_id", "access_code"),
    )

class AvailabilitySlot(Base):
    __tablename__ = "availability_slots"
    slot_id: Mapped[str] = mapped_column(String, primary_key=True)
    specialist_id: Mapped[str] = mapped_column(String, nullable=False)
    available_from: Mapped[str] = mapped_column(String, nullable=False)
    available_until: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    updated_at: Mapped[str] = mapped_column(String, nullable=False)

class WorkloadRecord(Base):
    __tablename__ = "workload_records"
    record_id: Mapped[str] = mapped_column(String, primary_key=True)
    specialist_id: Mapped[str] = mapped_column(String, nullable=False)
    active_assignment_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    assigned_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    after_hours_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    overnight_incident_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    recent_interruption_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[str] = mapped_column(String, nullable=False)

class Reservation(Base):
    __tablename__ = "reservations"
    reservation_id: Mapped[str] = mapped_column(String, primary_key=True)
    specialist_id: Mapped[str] = mapped_column(String, nullable=False)
    escalation_id: Mapped[str] = mapped_column(String, nullable=False)
    start_at: Mapped[str] = mapped_column(String, nullable=False)
    end_at: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False)
    idempotency_key: Mapped[Optional[str]] = mapped_column(String, unique=True, nullable=True)
    created_at: Mapped[str] = mapped_column(String, nullable=False)
    updated_at: Mapped[str] = mapped_column(String, nullable=False)

class FailureMode(Base):
    __tablename__ = "failure_modes"
    mode_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    mode: Mapped[str] = mapped_column(String, nullable=False)
    enabled: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    delay_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    remaining_failures: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    updated_at: Mapped[str] = mapped_column(String, nullable=False)
