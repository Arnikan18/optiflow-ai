from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, CheckConstraint, DateTime, Float, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.base import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Specialist(Base):
    __tablename__ = "specialists"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    specialist_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String(254), nullable=True, unique=True, index=True)
    capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    current_workload: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    availability: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    completed_assignments_30d: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sla_success_rate_30d: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    average_resolution_minutes_30d: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    assignment_acceptance_rate_30d: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    capacity_reliability_rate_30d: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )

    skills: Mapped[list["SpecialistSkill"]] = relationship(
        back_populates="specialist",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    reservations: Mapped[list["Reservation"]] = relationship(back_populates="specialist", lazy="selectin")

    __table_args__ = (
        CheckConstraint("capacity >= 1", name="ck_specialists_capacity_positive"),
        CheckConstraint("current_workload >= 0", name="ck_specialists_workload_nonnegative"),
        CheckConstraint("current_workload <= capacity", name="ck_specialists_workload_capacity"),
        CheckConstraint(
            "completed_assignments_30d >= 0",
            name="ck_specialists_completed_assignments_30d_nonnegative",
        ),
        CheckConstraint(
            "sla_success_rate_30d IS NULL OR sla_success_rate_30d BETWEEN 0 AND 100",
            name="ck_specialists_sla_success_rate_30d_range",
        ),
        CheckConstraint(
            "average_resolution_minutes_30d IS NULL OR average_resolution_minutes_30d > 0",
            name="ck_specialists_average_resolution_30d_positive",
        ),
        CheckConstraint(
            "assignment_acceptance_rate_30d IS NULL OR assignment_acceptance_rate_30d BETWEEN 0 AND 100",
            name="ck_specialists_assignment_acceptance_rate_30d_range",
        ),
        CheckConstraint(
            "capacity_reliability_rate_30d IS NULL OR capacity_reliability_rate_30d BETWEEN 0 AND 100",
            name="ck_specialists_capacity_reliability_rate_30d_range",
        ),
    )


class SpecialistSkill(Base):
    __tablename__ = "specialist_skills"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    specialist_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("specialists.specialist_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    skill: Mapped[str] = mapped_column(String(80), nullable=False, index=True)

    specialist: Mapped[Specialist] = relationship(back_populates="skills")

    __table_args__ = (
        UniqueConstraint("specialist_id", "skill", name="uq_specialist_skill"),
    )


class Reservation(Base):
    __tablename__ = "reservations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    reservation_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    run_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    specialist_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("specialists.specialist_id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    incident_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    confirmed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    cancellation_reason: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )

    specialist: Mapped[Specialist] = relationship(back_populates="reservations")

    __table_args__ = (
        CheckConstraint(
            "status IN ('TENTATIVE', 'CONFIRMED', 'CANCELLED', 'EXPIRED')",
            name="ck_reservations_status",
        ),
        Index("ix_reservations_specialist_incident_status", "specialist_id", "incident_id", "status"),
    )


class FailureMode(Base):
    __tablename__ = "failure_modes"

    mode_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    mode: Mapped[str] = mapped_column(String, nullable=False)
    enabled: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    delay_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    remaining_failures: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    updated_at: Mapped[str] = mapped_column(String, nullable=False)
