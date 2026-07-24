from datetime import datetime, timezone

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import FailureMode, Incident


def _utc_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def build_seed_incidents() -> list[Incident]:
    created_at = _utc_datetime("2026-07-22T10:00:00Z")
    return [
        Incident(
            incident_id="INC-ALPHA-001",
            customer_id="CUS-ALPHA",
            title="Payment API intermittently failing",
            description="Checkout requests intermittently return gateway errors for payment confirmations.",
            priority="CRITICAL",
            status="OPEN",
            sla_deadline=_utc_datetime("2026-07-22T12:00:00Z"),
            assigned_specialist_id=None,
            created_at=created_at,
            updated_at=created_at,
        ),
        Incident(
            incident_id="INC-NOVA-001",
            customer_id="CUS-NOVA",
            title="Enterprise onboarding blocked",
            description="SAML configuration issue is blocking a scheduled production launch.",
            priority="HIGH",
            status="IN_PROGRESS",
            sla_deadline=_utc_datetime("2099-07-25T10:00:00Z"),
            assigned_specialist_id="SPEC-NIMAL",
            created_at=created_at,
            updated_at=created_at,
        ),
        Incident(
            incident_id="INC-GREEN-001",
            customer_id="CUS-GREEN",
            title="Reporting export defect",
            description="Large report exports fail for logistics analytics users.",
            priority="MEDIUM",
            status="OPEN",
            sla_deadline=_utc_datetime("2099-07-27T10:00:00Z"),
            assigned_specialist_id=None,
            created_at=created_at,
            updated_at=created_at,
        ),
        Incident(
            incident_id="INC-MEDI-001",
            customer_id="CUS-MEDI",
            title="Security questionnaire review",
            description="Annual security questionnaire needed specialist review before renewal.",
            priority="LOW",
            status="RESOLVED",
            sla_deadline=_utc_datetime("2026-07-23T10:00:00Z"),
            assigned_specialist_id="SPEC-MAYA",
            created_at=created_at,
            updated_at=_utc_datetime("2026-07-23T11:00:00Z"),
        ),
        Incident(
            incident_id="INC-OMEGA-001",
            customer_id="CUS-OMEGA",
            title="Legacy data import completed",
            description="Historical import issue retained for closed-incident retrieval checks.",
            priority="HIGH",
            status="CLOSED",
            sla_deadline=_utc_datetime("2026-07-21T18:00:00Z"),
            assigned_specialist_id="SPEC-DANIEL",
            created_at=created_at,
            updated_at=_utc_datetime("2026-07-22T13:00:00Z"),
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


async def seed_database(session: AsyncSession) -> int:
    await session.execute(delete(Incident))
    session.add_all(build_seed_incidents())
    await ensure_failure_mode(session)
    await session.commit()
    return len(build_seed_incidents())


async def seed_incidents_if_empty(session: AsyncSession) -> int:
    result = await session.execute(select(func.count(Incident.id)))
    existing = result.scalar_one() or 0
    await ensure_failure_mode(session)
    if existing:
        await session.commit()
        return 0

    incidents = build_seed_incidents()
    session.add_all(incidents)
    await session.commit()
    return len(incidents)
