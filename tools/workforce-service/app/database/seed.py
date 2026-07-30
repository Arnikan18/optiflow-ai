from datetime import datetime, timezone

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import FailureMode, Reservation, Specialist, SpecialistSkill


def _utc_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def _specialist(
    specialist_id: str,
    name: str,
    email: str,
    skills: list[str],
    capacity: int,
    current_workload: int,
    availability: bool,
    active: bool,
    completed_assignments_30d: int,
    sla_success_rate_30d: float,
    average_resolution_minutes_30d: int,
    assignment_acceptance_rate_30d: float,
    capacity_reliability_rate_30d: float,
) -> Specialist:
    created_at = _utc_datetime("2026-07-22T10:00:00Z")
    specialist = Specialist(
        specialist_id=specialist_id,
        name=name,
        email=email,
        capacity=capacity,
        current_workload=current_workload,
        availability=availability,
        active=active,
        completed_assignments_30d=completed_assignments_30d,
        sla_success_rate_30d=sla_success_rate_30d,
        average_resolution_minutes_30d=average_resolution_minutes_30d,
        assignment_acceptance_rate_30d=assignment_acceptance_rate_30d,
        capacity_reliability_rate_30d=capacity_reliability_rate_30d,
        created_at=created_at,
        updated_at=created_at,
    )
    specialist.skills = [SpecialistSkill(specialist_id=specialist_id, skill=skill) for skill in skills]
    return specialist


def build_seed_specialists() -> list[Specialist]:
    return [
        _specialist(
            "SPEC-MAYA",
            "Maya Sen",
            "maya.sen@example.test",
            ["billing", "payments", "api-integration", "technical"],
            2,
            0,
            True,
            True,
            38,
            96.0,
            72,
            94.0,
            97.0,
        ),
        _specialist(
            "SPEC-DANIEL",
            "Daniel Ruiz",
            "daniel.ruiz@example.test",
            ["technical", "enterprise-support", "mobile", "security"],
            2,
            1,
            True,
            True,
            31,
            91.0,
            88,
            89.0,
            95.0,
        ),
        _specialist(
            "SPEC-NIMAL",
            "Nimal Perera",
            "nimal.perera@example.test",
            ["identity", "saml", "enterprise-onboarding", "security"],
            1,
            1,
            True,
            True,
            27,
            98.0,
            64,
            96.0,
            99.0,
        ),
        _specialist(
            "SPEC-PRIYA",
            "Priya Raman",
            "priya.raman@example.test",
            ["account-management", "billing"],
            3,
            0,
            False,
            True,
            24,
            93.0,
            80,
            92.0,
            96.0,
        ),
        _specialist(
            "SPEC-KAI",
            "Kai Morgan",
            "kai.morgan@example.test",
            ["technical", "security"],
            2,
            0,
            True,
            False,
            12,
            88.0,
            110,
            85.0,
            82.0,
        ),
        _specialist(
            "SPEC-LEILA",
            "Leila Hassan",
            "leila.hassan@example.test",
            ["clinical-data", "queue-operations", "integration", "security"],
            3,
            1,
            True,
            True,
            35,
            97.0,
            76,
            95.0,
            98.0,
        ),
        _specialist(
            "SPEC-OMAR",
            "Omar Silva",
            "omar.silva@example.test",
            ["data-integration", "roster-sync", "data-reporting", "exports", "technical"],
            3,
            0,
            True,
            True,
            29,
            94.0,
            84,
            91.0,
            96.0,
        ),
        _specialist(
            "SPEC-SOFIA",
            "Sofia Chen",
            "sofia.chen@example.test",
            ["enterprise-onboarding", "data-validation", "identity", "solution-architecture"],
            2,
            0,
            False,
            True,
            22,
            95.0,
            90,
            90.0,
            94.0,
        ),
    ]


def build_seed_reservations() -> list[Reservation]:
    created_at = _utc_datetime("2026-07-22T10:00:00Z")
    return [
        Reservation(
            reservation_id="RES-MAYA-TENTATIVE",
            specialist_id="SPEC-MAYA",
            incident_id="INC-ALPHA-001",
            status="TENTATIVE",
            created_at=created_at,
            expires_at=_utc_datetime("2099-07-24T10:05:00Z"),
            updated_at=created_at,
        ),
        Reservation(
            reservation_id="RES-DANIEL-CONFIRMED",
            specialist_id="SPEC-DANIEL",
            incident_id="INC-NOVA-001",
            status="CONFIRMED",
            created_at=created_at,
            expires_at=_utc_datetime("2026-07-22T10:05:00Z"),
            confirmed_at=_utc_datetime("2026-07-22T10:02:00Z"),
            updated_at=_utc_datetime("2026-07-22T10:02:00Z"),
        ),
        Reservation(
            reservation_id="RES-NIMAL-CONFIRMED",
            specialist_id="SPEC-NIMAL",
            incident_id="INC-MEDI-001",
            status="CONFIRMED",
            created_at=created_at,
            expires_at=_utc_datetime("2026-07-22T10:05:00Z"),
            confirmed_at=_utc_datetime("2026-07-22T10:03:00Z"),
            updated_at=_utc_datetime("2026-07-22T10:03:00Z"),
        ),
        Reservation(
            reservation_id="RES-PRIYA-CANCELLED",
            specialist_id="SPEC-PRIYA",
            incident_id="INC-CANCELLED-001",
            status="CANCELLED",
            created_at=created_at,
            expires_at=_utc_datetime("2026-07-22T10:05:00Z"),
            cancelled_at=_utc_datetime("2026-07-22T10:04:00Z"),
            updated_at=_utc_datetime("2026-07-22T10:04:00Z"),
        ),
        Reservation(
            reservation_id="RES-DANIEL-EXPIRED",
            specialist_id="SPEC-DANIEL",
            incident_id="INC-EXPIRED-001",
            status="TENTATIVE",
            created_at=created_at,
            expires_at=_utc_datetime("2026-07-22T10:05:00Z"),
            updated_at=created_at,
        ),
        Reservation(
            reservation_id="RES-LEILA-CONFIRMED",
            specialist_id="SPEC-LEILA",
            incident_id="INC-HARBOR-001",
            status="CONFIRMED",
            created_at=created_at,
            expires_at=_utc_datetime("2026-07-22T10:05:00Z"),
            confirmed_at=_utc_datetime("2026-07-22T10:02:00Z"),
            updated_at=_utc_datetime("2026-07-22T10:02:00Z"),
        ),
        Reservation(
            reservation_id="RES-OMAR-TENTATIVE",
            specialist_id="SPEC-OMAR",
            incident_id="INC-SUMMIT-001",
            status="TENTATIVE",
            created_at=created_at,
            expires_at=_utc_datetime("2099-07-24T10:05:00Z"),
            updated_at=created_at,
        ),
        Reservation(
            reservation_id="RES-SOFIA-CANCELLED",
            specialist_id="SPEC-SOFIA",
            incident_id="INC-NOVA-002",
            status="CANCELLED",
            created_at=created_at,
            expires_at=_utc_datetime("2026-07-22T10:05:00Z"),
            cancelled_at=_utc_datetime("2026-07-22T10:04:00Z"),
            cancellation_reason="Specialist is not available during the launch window.",
            updated_at=_utc_datetime("2026-07-22T10:04:00Z"),
        ),
    ]


async def ensure_failure_mode(session: AsyncSession) -> None:
    result = await session.execute(select(FailureMode).limit(1))
    if result.scalar_one_or_none() is not None:
        return

    session.add(
        FailureMode(
            mode="TIMEOUT",
            enabled=0,
            delay_ms=5000,
            remaining_failures=0,
            updated_at=datetime.now(timezone.utc).isoformat(),
        )
    )


async def seed_database(session: AsyncSession) -> dict[str, int]:
    await session.execute(delete(Reservation))
    await session.execute(delete(SpecialistSkill))
    await session.execute(delete(Specialist))
    specialists = build_seed_specialists()
    reservations = build_seed_reservations()
    session.add_all(specialists)
    session.add_all(reservations)
    await ensure_failure_mode(session)
    await session.commit()
    return {"specialist_count": len(specialists), "reservation_count": len(reservations)}


async def seed_workforce_if_empty(session: AsyncSession) -> dict[str, int]:
    result = await session.execute(select(func.count(Specialist.id)))
    existing = result.scalar_one() or 0
    await ensure_failure_mode(session)
    if existing:
        await session.commit()
        return {"specialist_count": 0, "reservation_count": 0}

    specialists = build_seed_specialists()
    reservations = build_seed_reservations()
    session.add_all(specialists)
    session.add_all(reservations)
    await session.commit()
    return {"specialist_count": len(specialists), "reservation_count": len(reservations)}
