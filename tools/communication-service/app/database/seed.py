from datetime import datetime, timezone

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import AssignmentRequest, ConfiguredResponse, FailureMode, Notification


def _utc_datetime(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def build_seed_assignment_requests() -> list[AssignmentRequest]:
    created_at = _utc_datetime("2026-07-22T10:00:00Z")
    return [
        AssignmentRequest(
            request_id="AR-PENDING-001",
            incident_id="INC-ALPHA-001",
            specialist_id="SPEC-MAYA",
            message="Please review and accept this critical payment incident assignment.",
            status="PENDING",
            created_at=created_at,
            expires_at=_utc_datetime("2099-07-24T10:15:00Z"),
            updated_at=created_at,
        ),
        AssignmentRequest(
            request_id="AR-ACCEPTED-001",
            incident_id="INC-NOVA-001",
            specialist_id="SPEC-DANIEL",
            message="Please take ownership of the enterprise onboarding incident.",
            status="ACCEPTED",
            created_at=created_at,
            expires_at=_utc_datetime("2099-07-24T10:15:00Z"),
            responded_at=_utc_datetime("2026-07-22T10:05:00Z"),
            response_note="Available now.",
            response_reason="Available now.",
            updated_at=_utc_datetime("2026-07-22T10:05:00Z"),
        ),
        AssignmentRequest(
            request_id="AR-REJECTED-001",
            incident_id="INC-MEDI-001",
            specialist_id="SPEC-NIMAL",
            message="Please review this security questionnaire incident.",
            status="REJECTED",
            created_at=created_at,
            expires_at=_utc_datetime("2099-07-24T10:15:00Z"),
            responded_at=_utc_datetime("2026-07-22T10:10:00Z"),
            response_note="Capacity is already committed.",
            response_reason="Capacity is already committed.",
            updated_at=_utc_datetime("2026-07-22T10:10:00Z"),
        ),
        AssignmentRequest(
            request_id="AR-EXPIRED-001",
            incident_id="INC-EXPIRED-001",
            specialist_id="SPEC-PRIYA",
            message="Expired assignment request retained for lifecycle checks.",
            status="PENDING",
            created_at=_utc_datetime("2020-01-01T10:00:00Z"),
            expires_at=_utc_datetime("2020-01-01T10:15:00Z"),
            updated_at=_utc_datetime("2020-01-01T10:00:00Z"),
        ),
        AssignmentRequest(
            request_id="AR-CANCELLED-001",
            incident_id="INC-CANCELLED-001",
            specialist_id="SPEC-KAI",
            message="Cancelled request retained for terminal-state checks.",
            status="CANCELLED",
            created_at=created_at,
            expires_at=_utc_datetime("2099-07-24T10:15:00Z"),
            updated_at=_utc_datetime("2026-07-22T10:20:00Z"),
        ),
    ]


def build_seed_notifications() -> list[Notification]:
    created_at = _utc_datetime("2026-07-22T10:30:00Z")
    return [
        Notification(
            notification_id="NOT-EMAIL-DELIVERED",
            recipient="maya.sen@example.test",
            channel="EMAIL",
            subject="New Incident Assignment",
            message="You have received assignment request AR-PENDING-001.",
            status="DELIVERED",
            idempotency_key="seed-email-ar-pending",
            related_request_id="AR-PENDING-001",
            created_at=created_at,
            attempted_at=created_at,
            delivered_at=created_at,
            attempt_count=1,
            updated_at=created_at,
        ),
        Notification(
            notification_id="NOT-SMS-DELIVERED",
            recipient="+15550101010",
            channel="SMS",
            subject=None,
            message="OptiFlow assignment request AR-ACCEPTED-001.",
            status="DELIVERED",
            idempotency_key="seed-sms-ar-accepted",
            related_request_id="AR-ACCEPTED-001",
            created_at=created_at,
            attempted_at=created_at,
            delivered_at=created_at,
            attempt_count=1,
            updated_at=created_at,
        ),
        Notification(
            notification_id="NOT-INAPP-DELIVERED",
            recipient="SPEC-DANIEL",
            channel="IN_APP",
            subject="Assignment update",
            message="Assignment request AR-ACCEPTED-001 was accepted.",
            status="DELIVERED",
            idempotency_key="seed-inapp-ar-accepted",
            related_request_id="AR-ACCEPTED-001",
            created_at=created_at,
            attempted_at=created_at,
            delivered_at=created_at,
            attempt_count=1,
            updated_at=created_at,
        ),
        Notification(
            notification_id="NOT-FAILED-001",
            recipient="fail@example.test",
            channel="EMAIL",
            subject="Simulated failed delivery",
            message="This seeded notification demonstrates controlled failure state.",
            status="FAILED",
            idempotency_key="seed-failed-email",
            related_request_id="AR-REJECTED-001",
            created_at=created_at,
            attempted_at=created_at,
            failure_reason="Simulated delivery failed",
            attempt_count=1,
            updated_at=created_at,
        ),
        Notification(
            notification_id="NOT-WEBHOOK-DELIVERED",
            recipient="webhook-demo-destination",
            channel="WEBHOOK",
            subject="Portfolio event",
            message="Standalone simulated webhook notification.",
            status="DELIVERED",
            idempotency_key="seed-webhook-standalone",
            related_request_id=None,
            created_at=created_at,
            attempted_at=created_at,
            delivered_at=created_at,
            attempt_count=1,
            updated_at=created_at,
        ),
    ]


async def ensure_failure_mode(session: AsyncSession) -> None:
    result = await session.execute(select(FailureMode).limit(1))
    if result.scalar_one_or_none() is not None:
        return

    session.add(
        FailureMode(
            mode="TIMEOUT",
            failure_type="TIMEOUT",
            enabled=0,
            status_code=503,
            delay_seconds=0,
            delay_ms=5000,
            affected_endpoint=None,
            scope=None,
            remaining_failures=0,
            updated_at=datetime.now(timezone.utc).isoformat(),
        )
    )


async def seed_database(session: AsyncSession) -> dict[str, int]:
    await session.execute(delete(Notification))
    await session.execute(delete(AssignmentRequest))
    await session.execute(delete(ConfiguredResponse))
    await session.execute(delete(FailureMode))

    assignments = build_seed_assignment_requests()
    notifications = build_seed_notifications()
    session.add_all(assignments)
    await session.flush()
    session.add_all(notifications)
    await ensure_failure_mode(session)
    await session.commit()
    return {"assignment_request_count": len(assignments), "notification_count": len(notifications)}


async def seed_communication_if_empty(session: AsyncSession) -> dict[str, int]:
    result = await session.execute(select(func.count(AssignmentRequest.id)))
    existing = result.scalar_one() or 0
    await ensure_failure_mode(session)
    if existing:
        await session.commit()
        return {"assignment_request_count": 0, "notification_count": 0}

    assignments = build_seed_assignment_requests()
    notifications = build_seed_notifications()
    session.add_all(assignments)
    await session.flush()
    session.add_all(notifications)
    await session.commit()
    return {"assignment_request_count": len(assignments), "notification_count": len(notifications)}
