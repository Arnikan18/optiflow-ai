from dataclasses import dataclass
from datetime import datetime, timezone
from math import ceil
from typing import Optional

from sqlalchemy import delete, func, or_, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Incident
from app.database.seed import build_seed_incidents, ensure_failure_mode
from app.schemas.requests import (
    IncidentAssignmentRequest,
    IncidentAssignmentVerificationRequest,
    IncidentCreateRequest,
    IncidentSimulationFieldUpdateRequest,
    IncidentSimulationLoadStateRequest,
    IncidentSimulationResolveRequest,
    IncidentStatusUpdateRequest,
    normalize_customer_id,
    normalize_datetime,
    normalize_incident_id,
    normalize_priority,
    normalize_search,
    normalize_specialist_id,
    normalize_status,
)


ACTIVE_STATUSES = ("OPEN", "IN_PROGRESS")
CLOSED_STATUSES = ("RESOLVED", "CLOSED")

ALLOWED_STATUS_TRANSITIONS = {
    "OPEN": {"IN_PROGRESS", "CLOSED"},
    "IN_PROGRESS": {"OPEN", "RESOLVED", "CLOSED"},
    "RESOLVED": {"IN_PROGRESS", "CLOSED"},
    "CLOSED": set(),
}


class IncidentError(Exception):
    def __init__(self, status_code: int, error_code: str, message: str) -> None:
        self.status_code = status_code
        self.error_code = error_code
        self.message = message
        super().__init__(message)


@dataclass(frozen=True)
class IncidentListResult:
    incidents: list[Incident]
    page: int
    page_size: int
    total_items: int
    total_pages: int


def _database_error() -> IncidentError:
    return IncidentError(503, "INCIDENT_503", "Incident database operation failed")


async def list_incidents(
    session: AsyncSession,
    *,
    page: int,
    page_size: int,
    status: Optional[str] = None,
    priority: Optional[str] = None,
    customer_id: Optional[str] = None,
    assigned_specialist_id: Optional[str] = None,
    unassigned: Optional[bool] = None,
    overdue: Optional[bool] = None,
    search: Optional[str] = None,
    sla_before=None,
    sla_after=None,
) -> IncidentListResult:
    conditions = []

    try:
        if status is not None:
            conditions.append(Incident.status == normalize_status(status))
        if priority is not None:
            conditions.append(Incident.priority == normalize_priority(priority))
        if customer_id is not None:
            conditions.append(Incident.customer_id == normalize_customer_id(customer_id))
        if assigned_specialist_id is not None:
            conditions.append(Incident.assigned_specialist_id == normalize_specialist_id(assigned_specialist_id))
        if unassigned is True and assigned_specialist_id is not None:
            raise IncidentError(422, "INCIDENT_422", "unassigned cannot be combined with assigned_specialist_id")
        if unassigned is True:
            conditions.append(Incident.assigned_specialist_id.is_(None))
        elif unassigned is False:
            conditions.append(Incident.assigned_specialist_id.is_not(None))

        if sla_after is not None:
            sla_after = normalize_datetime(sla_after)
            conditions.append(Incident.sla_deadline >= sla_after)
        if sla_before is not None:
            sla_before = normalize_datetime(sla_before)
            conditions.append(Incident.sla_deadline <= sla_before)
        if sla_after is not None and sla_before is not None and sla_after > sla_before:
            raise IncidentError(422, "INCIDENT_422", "sla_after must not be after sla_before")
    except ValueError as exc:
        raise IncidentError(422, "INCIDENT_422", str(exc)) from exc

    if overdue is not None:
        now_utc = datetime.now(timezone.utc)
        if overdue:
            conditions.append(Incident.sla_deadline < now_utc)
            conditions.append(Incident.status.not_in(CLOSED_STATUSES))
        else:
            conditions.append(or_(Incident.sla_deadline >= now_utc, Incident.status.in_(CLOSED_STATUSES)))

    normalized_search = normalize_search(search)
    if normalized_search:
        pattern = f"%{normalized_search}%"
        conditions.append(
            or_(
                Incident.incident_id.ilike(pattern),
                Incident.title.ilike(pattern),
                Incident.description.ilike(pattern),
            )
        )

    try:
        total_result = await session.execute(select(func.count(Incident.id)).where(*conditions))
        total_items = total_result.scalar_one() or 0
        total_pages = ceil(total_items / page_size) if total_items else 0
        result = await session.execute(
            select(Incident)
            .where(*conditions)
            .order_by(Incident.sla_deadline.asc(), Incident.incident_id.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    except SQLAlchemyError as exc:
        raise _database_error() from exc

    return IncidentListResult(
        incidents=list(result.scalars().all()),
        page=page,
        page_size=page_size,
        total_items=total_items,
        total_pages=total_pages,
    )


async def get_incident(session: AsyncSession, incident_id: str) -> Incident:
    try:
        normalized_id = normalize_incident_id(incident_id)
    except ValueError as exc:
        raise IncidentError(422, "INCIDENT_422", str(exc)) from exc

    try:
        result = await session.execute(select(Incident).where(Incident.incident_id == normalized_id))
    except SQLAlchemyError as exc:
        raise _database_error() from exc

    incident = result.scalar_one_or_none()
    if incident is None:
        raise IncidentError(404, "INCIDENT_404", "Incident not found")
    return incident


async def create_incident(session: AsyncSession, payload: IncidentCreateRequest) -> Incident:
    try:
        existing = await session.execute(select(Incident.id).where(Incident.incident_id == payload.incident_id))
        if existing.scalar_one_or_none() is not None:
            raise IncidentError(409, "INCIDENT_409", "Incident identifier already exists")

        incident = Incident(**payload.model_dump())
        session.add(incident)
        await session.commit()
        await session.refresh(incident)
        return incident
    except IncidentError:
        await session.rollback()
        raise
    except IntegrityError as exc:
        await session.rollback()
        raise IncidentError(409, "INCIDENT_409", "Incident identifier already exists") from exc
    except SQLAlchemyError as exc:
        await session.rollback()
        raise _database_error() from exc


async def load_simulation_incidents(
    session: AsyncSession,
    payload: IncidentSimulationLoadStateRequest,
) -> dict[str, int | str]:
    try:
        await session.execute(delete(Incident))
        incidents = []
        for item in payload.incidents:
            data = item.model_dump(exclude_none=True)
            incidents.append(Incident(**data))
        session.add_all(incidents)
        await ensure_failure_mode(session)
        await session.commit()
        return {"scenario_id": payload.scenario_id, "incident_count": len(incidents)}
    except SQLAlchemyError as exc:
        await session.rollback()
        raise _database_error() from exc


async def update_incident_simulation_fields(
    session: AsyncSession,
    incident_id: str,
    payload: IncidentSimulationFieldUpdateRequest,
) -> Incident:
    incident = await get_incident(session, incident_id)
    if incident.status in CLOSED_STATUSES:
        raise IncidentError(409, "INCIDENT_409", "Resolved or closed incidents cannot be changed by simulation")

    changed = False
    if payload.priority is not None and incident.priority != payload.priority:
        incident.priority = payload.priority
        changed = True
    if payload.sla_deadline is not None and incident.sla_deadline != payload.sla_deadline:
        incident.sla_deadline = payload.sla_deadline
        changed = True
    if (
        payload.estimated_effort_minutes is not None
        and incident.estimated_effort_minutes != payload.estimated_effort_minutes
    ):
        incident.estimated_effort_minutes = payload.estimated_effort_minutes
        changed = True

    if not changed:
        return incident

    try:
        incident.updated_at = datetime.now(timezone.utc)
        session.add(incident)
        await session.commit()
        await session.refresh(incident)
        return incident
    except SQLAlchemyError as exc:
        await session.rollback()
        raise _database_error() from exc


async def resolve_incident_for_simulation(
    session: AsyncSession,
    incident_id: str,
    payload: IncidentSimulationResolveRequest,
) -> Incident:
    if payload.incident_id is not None and payload.incident_id != normalize_incident_id(incident_id):
        raise IncidentError(422, "INCIDENT_422", "payload incident_id must match path incident_id")

    incident = await get_incident(session, incident_id)
    if incident.status in CLOSED_STATUSES:
        return incident
    if incident.status not in ACTIVE_STATUSES:
        raise IncidentError(409, "INCIDENT_409", "Incident cannot be resolved in its current status")

    resolved_at = payload.resolved_at or datetime.now(timezone.utc)
    incident.status = "RESOLVED"
    incident.resolved_at = resolved_at
    incident.updated_at = resolved_at
    incident.assigned_specialist_id = None
    incident.assignment_run_id = None
    incident.assignment_idempotency_key = None
    incident.assigned_at = None
    try:
        session.add(incident)
        await session.commit()
        await session.refresh(incident)
        return incident
    except SQLAlchemyError as exc:
        await session.rollback()
        raise _database_error() from exc


async def update_incident_status(
    session: AsyncSession,
    incident_id: str,
    payload: IncidentStatusUpdateRequest,
) -> Incident:
    incident = await get_incident(session, incident_id)
    target_status = payload.status

    if incident.status == target_status:
        return incident

    if target_status not in ALLOWED_STATUS_TRANSITIONS[incident.status]:
        raise IncidentError(409, "INCIDENT_409", "Invalid incident status transition")

    incident.status = target_status
    try:
        session.add(incident)
        await session.commit()
        await session.refresh(incident)
        return incident
    except SQLAlchemyError as exc:
        await session.rollback()
        raise _database_error() from exc


async def assign_specialist(
    session: AsyncSession,
    incident_id: str,
    payload: IncidentAssignmentRequest,
) -> Incident:
    incident = await get_incident(session, incident_id)

    if incident.status in CLOSED_STATUSES:
        raise IncidentError(409, "INCIDENT_409", "Resolved or closed incidents cannot be assigned")

    if incident.assigned_specialist_id == payload.specialist_id:
        changed = False
        if payload.run_id is not None and incident.assignment_run_id != payload.run_id:
            incident.assignment_run_id = payload.run_id
            changed = True
        if payload.idempotency_key is not None and incident.assignment_idempotency_key != payload.idempotency_key:
            incident.assignment_idempotency_key = payload.idempotency_key
            changed = True
        if not changed:
            return incident
        try:
            session.add(incident)
            await session.commit()
            await session.refresh(incident)
            return incident
        except SQLAlchemyError as exc:
            await session.rollback()
            raise _database_error() from exc

    if incident.assigned_specialist_id and incident.status not in ACTIVE_STATUSES:
        raise IncidentError(409, "INCIDENT_409", "Incident cannot be reassigned in its current status")

    incident.assigned_specialist_id = payload.specialist_id
    incident.assignment_run_id = payload.run_id
    incident.assignment_idempotency_key = payload.idempotency_key
    incident.assigned_at = datetime.now(timezone.utc)
    try:
        session.add(incident)
        await session.commit()
        await session.refresh(incident)
        return incident
    except SQLAlchemyError as exc:
        await session.rollback()
        raise _database_error() from exc


async def verify_incident_assignment(session: AsyncSession, payload: IncidentAssignmentVerificationRequest) -> dict:
    checked_at = datetime.now(timezone.utc)
    expected_values = {
        "run_id": payload.expected_run_id,
        "specialist_id": payload.expected_specialist_id,
    }

    try:
        result = await session.execute(select(Incident).where(Incident.incident_id == payload.incident_id))
        incident = result.scalar_one_or_none()
    except SQLAlchemyError as exc:
        raise _database_error() from exc

    if incident is None:
        return {
            "verified": False,
            "result": "not_found",
            "incident_id": payload.incident_id,
            "expected_values": expected_values,
            "actual_values": None,
            "failed_checks": ["incident_not_found"],
            "checked_at": checked_at,
            "assignment_status": None,
        }

    assignment_status = _assignment_status(incident)
    actual_values = {
        "assigned_specialist_id": incident.assigned_specialist_id,
        "assignment_run_id": incident.assignment_run_id,
        "assignment_idempotency_key": incident.assignment_idempotency_key,
        "incident_status": incident.status,
        "assigned_at": incident.assigned_at,
    }

    failed_checks: list[str] = []
    if incident.assigned_specialist_id is None:
        failed_checks.append("incident_unassigned")
    elif incident.assigned_specialist_id != payload.expected_specialist_id:
        failed_checks.append("specialist_id_mismatch")

    run_matches = (
        incident.assignment_run_id == payload.expected_run_id
        or incident.assignment_idempotency_key == payload.expected_run_id
    )
    if not run_matches:
        failed_checks.append("run_id_mismatch")
    if assignment_status == "invalid":
        failed_checks.append("assignment_status_invalid")

    if incident.assigned_specialist_id is None:
        result_status = "pending"
    elif failed_checks:
        result_status = "inconsistent"
    else:
        result_status = "verified"

    return {
        "verified": result_status == "verified",
        "result": result_status,
        "incident_id": incident.incident_id,
        "expected_values": expected_values,
        "actual_values": actual_values,
        "failed_checks": failed_checks,
        "checked_at": checked_at,
        "assignment_status": assignment_status,
    }


def _assignment_status(incident: Incident) -> str:
    if incident.assigned_specialist_id is None:
        return "pending"
    if incident.status in ACTIVE_STATUSES:
        return "active"
    if incident.status == "RESOLVED":
        return "completed"
    return "invalid"


async def seed_incidents_if_empty(session: AsyncSession) -> int:
    try:
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
    except SQLAlchemyError as exc:
        await session.rollback()
        raise _database_error() from exc


async def reset_incidents(session: AsyncSession) -> int:
    try:
        await session.execute(delete(Incident))
        incidents = build_seed_incidents()
        session.add_all(incidents)
        await ensure_failure_mode(session)
        await session.commit()
        return len(incidents)
    except SQLAlchemyError as exc:
        await session.rollback()
        raise _database_error() from exc


def incident_to_legacy_escalation(incident: Incident) -> dict:
    return {
        "escalationId": incident.incident_id,
        "customerId": incident.customer_id,
        "title": incident.title,
        "severity": incident.priority,
        "slaDeadline": incident.sla_deadline,
        "status": incident.status,
        "requiredSkills": [],
        "requiredAccess": [],
        "requiredDurationMinutes": None,
        "workaroundStatus": None,
        "currentSpecialistId": incident.assigned_specialist_id,
        "sourceUpdatedAt": incident.updated_at,
    }


async def list_legacy_escalations(session: AsyncSession, *, active_only: bool = False) -> list[dict]:
    conditions = []
    if active_only:
        conditions.append(Incident.status.not_in(CLOSED_STATUSES))

    try:
        result = await session.execute(
            select(Incident).where(*conditions).order_by(Incident.sla_deadline.asc(), Incident.incident_id.asc())
        )
    except SQLAlchemyError as exc:
        raise _database_error() from exc

    return [incident_to_legacy_escalation(incident) for incident in result.scalars().all()]


async def get_legacy_escalation(session: AsyncSession, escalation_id: str) -> dict:
    incident = await get_incident(session, escalation_id)
    return incident_to_legacy_escalation(incident)
