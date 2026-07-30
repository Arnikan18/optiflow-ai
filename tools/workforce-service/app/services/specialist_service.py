from dataclasses import dataclass
from datetime import datetime, timezone
from math import ceil
from typing import Optional

from sqlalchemy import func, or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import Reservation, Specialist, SpecialistSkill
from app.schemas.requests import (
    WorkforceSimulationAvailabilityRequest,
    normalize_skill,
    normalize_specialist_id,
)


class WorkforceError(Exception):
    def __init__(self, status_code: int, error_code: str, message: str) -> None:
        self.status_code = status_code
        self.error_code = error_code
        self.message = message
        super().__init__(message)


@dataclass(frozen=True)
class SpecialistView:
    specialist: Specialist
    skills: list[str]
    active_pending_reservations: int

    @property
    def effective_workload(self) -> int:
        return self.specialist.current_workload + self.active_pending_reservations

    @property
    def available_capacity(self) -> int:
        return max(self.specialist.capacity - self.effective_workload, 0)

    @property
    def operationally_available(self) -> bool:
        return bool(self.specialist.active and self.specialist.availability and self.available_capacity > 0)


@dataclass(frozen=True)
class SpecialistListResult:
    specialists: list[SpecialistView]
    page: int
    page_size: int
    total_items: int
    total_pages: int


@dataclass(frozen=True)
class WorkloadView:
    specialist: Specialist
    tentative_reservation_count: int
    confirmed_reservation_count: int

    @property
    def assigned_count(self) -> int:
        return self.specialist.current_workload

    @property
    def effective_workload(self) -> int:
        return self.specialist.current_workload + self.tentative_reservation_count

    @property
    def available_capacity(self) -> int:
        return max(self.specialist.capacity - self.effective_workload, 0)

    @property
    def utilisation_percentage(self) -> float:
        if self.specialist.capacity <= 0:
            return 0.0
        return round((self.effective_workload / self.specialist.capacity) * 100, 2)


@dataclass(frozen=True)
class WorkloadListResult:
    workloads: list[WorkloadView]
    page: int
    page_size: int
    total_items: int
    total_pages: int


def _database_error() -> WorkforceError:
    return WorkforceError(503, "WORKFORCE_503", "Workforce database operation failed")


def _active_pending_subquery(now_utc: datetime):
    return (
        select(Reservation.specialist_id, func.count(Reservation.id).label("pending_count"))
        .where(Reservation.status == "TENTATIVE", Reservation.expires_at > now_utc)
        .group_by(Reservation.specialist_id)
        .subquery()
    )


def _pending_count_expr(pending_subquery):
    return func.coalesce(pending_subquery.c.pending_count, 0)


def _confirmed_count_subquery():
    return (
        select(Reservation.specialist_id, func.count(Reservation.id).label("confirmed_count"))
        .where(Reservation.status == "CONFIRMED")
        .group_by(Reservation.specialist_id)
        .subquery()
    )


def _confirmed_count_expr(confirmed_subquery):
    return func.coalesce(confirmed_subquery.c.confirmed_count, 0)


async def _skills_by_specialist(session: AsyncSession, specialist_ids: list[str]) -> dict[str, list[str]]:
    if not specialist_ids:
        return {}
    result = await session.execute(
        select(SpecialistSkill.specialist_id, SpecialistSkill.skill)
        .where(SpecialistSkill.specialist_id.in_(specialist_ids))
        .order_by(SpecialistSkill.skill.asc())
    )
    skills: dict[str, list[str]] = {specialist_id: [] for specialist_id in specialist_ids}
    for specialist_id, skill in result.all():
        skills.setdefault(specialist_id, []).append(skill)
    return skills


async def list_specialists(
    session: AsyncSession,
    *,
    page: int,
    page_size: int,
    active: Optional[bool] = None,
    availability: Optional[bool] = None,
    skill: Optional[str] = None,
    min_available_capacity: Optional[int] = None,
    search: Optional[str] = None,
    only_operationally_available: bool = False,
    required_capacity: int = 1,
) -> SpecialistListResult:
    now_utc = datetime.now(timezone.utc)
    pending = _active_pending_subquery(now_utc)
    pending_count = _pending_count_expr(pending)
    available_capacity = Specialist.capacity - Specialist.current_workload - pending_count

    conditions = []
    joins_skill = False

    try:
        if skill is not None:
            normalized_skill = normalize_skill(skill)
            conditions.append(SpecialistSkill.skill == normalized_skill)
            joins_skill = True
        if min_available_capacity is not None:
            if min_available_capacity < 0:
                raise WorkforceError(422, "WORKFORCE_422", "min_available_capacity must not be negative")
            conditions.append(available_capacity >= min_available_capacity)
        if only_operationally_available:
            if required_capacity < 1:
                raise WorkforceError(422, "WORKFORCE_422", "required_capacity must be at least 1")
            conditions.extend(
                [
                    Specialist.active.is_(True),
                    Specialist.availability.is_(True),
                    available_capacity >= required_capacity,
                ]
            )
        if active is not None:
            conditions.append(Specialist.active.is_(active))
        if availability is not None:
            conditions.append(Specialist.availability.is_(availability))
    except ValueError as exc:
        raise WorkforceError(422, "WORKFORCE_422", str(exc)) from exc

    if search is not None:
        normalized_search = search.strip()
        if normalized_search:
            pattern = f"%{normalized_search}%"
            conditions.append(
                or_(
                    Specialist.specialist_id.ilike(pattern),
                    Specialist.name.ilike(pattern),
                    Specialist.email.ilike(pattern),
                )
            )

    try:
        base = select(Specialist, pending_count.label("pending_count")).outerjoin(
            pending,
            Specialist.specialist_id == pending.c.specialist_id,
        )
        count_query = select(func.count(func.distinct(Specialist.id))).outerjoin(
            pending,
            Specialist.specialist_id == pending.c.specialist_id,
        )
        if joins_skill:
            base = base.join(SpecialistSkill, Specialist.specialist_id == SpecialistSkill.specialist_id)
            count_query = count_query.join(SpecialistSkill, Specialist.specialist_id == SpecialistSkill.specialist_id)

        total_result = await session.execute(count_query.where(*conditions))
        total_items = total_result.scalar_one() or 0
        total_pages = ceil(total_items / page_size) if total_items else 0
        result = await session.execute(
            base.where(*conditions)
            .group_by(Specialist.id, pending_count)
            .order_by(Specialist.specialist_id.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        rows = result.all()
        specialist_ids = [specialist.specialist_id for specialist, _ in rows]
        skills_map = await _skills_by_specialist(session, specialist_ids)
    except SQLAlchemyError as exc:
        raise _database_error() from exc

    views = [
        SpecialistView(
            specialist=specialist,
            skills=skills_map.get(specialist.specialist_id, []),
            active_pending_reservations=int(pending_count_value or 0),
        )
        for specialist, pending_count_value in rows
    ]
    return SpecialistListResult(
        specialists=views,
        page=page,
        page_size=page_size,
        total_items=total_items,
        total_pages=total_pages,
    )


async def list_workloads(session: AsyncSession, *, page: int, page_size: int) -> WorkloadListResult:
    now_utc = datetime.now(timezone.utc)
    tentative = _active_pending_subquery(now_utc)
    confirmed = _confirmed_count_subquery()
    tentative_count = _pending_count_expr(tentative)
    confirmed_count = _confirmed_count_expr(confirmed)

    try:
        total_result = await session.execute(select(func.count(Specialist.id)))
        total_items = total_result.scalar_one() or 0
        total_pages = ceil(total_items / page_size) if total_items else 0
        result = await session.execute(
            select(
                Specialist,
                tentative_count.label("tentative_count"),
                confirmed_count.label("confirmed_count"),
            )
            .outerjoin(tentative, Specialist.specialist_id == tentative.c.specialist_id)
            .outerjoin(confirmed, Specialist.specialist_id == confirmed.c.specialist_id)
            .group_by(Specialist.id, tentative_count, confirmed_count)
            .order_by(Specialist.specialist_id.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    except SQLAlchemyError as exc:
        raise _database_error() from exc

    return WorkloadListResult(
        workloads=[
            WorkloadView(
                specialist=specialist,
                tentative_reservation_count=int(tentative_value or 0),
                confirmed_reservation_count=int(confirmed_value or 0),
            )
            for specialist, tentative_value, confirmed_value in result.all()
        ],
        page=page,
        page_size=page_size,
        total_items=total_items,
        total_pages=total_pages,
    )


async def get_specialist(session: AsyncSession, specialist_id: str) -> SpecialistView:
    try:
        normalized_id = normalize_specialist_id(specialist_id)
    except ValueError as exc:
        raise WorkforceError(422, "WORKFORCE_422", str(exc)) from exc

    now_utc = datetime.now(timezone.utc)
    pending = _active_pending_subquery(now_utc)
    pending_count = _pending_count_expr(pending)
    try:
        result = await session.execute(
            select(Specialist, pending_count.label("pending_count"))
            .outerjoin(pending, Specialist.specialist_id == pending.c.specialist_id)
            .where(Specialist.specialist_id == normalized_id)
            .group_by(Specialist.id, pending_count)
        )
        row = result.one_or_none()
        if row is None:
            raise WorkforceError(404, "WORKFORCE_404", "Specialist not found")
        specialist, pending_count_value = row
        skills_map = await _skills_by_specialist(session, [specialist.specialist_id])
    except WorkforceError:
        raise
    except SQLAlchemyError as exc:
        raise _database_error() from exc

    return SpecialistView(
        specialist=specialist,
        skills=skills_map.get(specialist.specialist_id, []),
        active_pending_reservations=int(pending_count_value or 0),
    )


def specialist_view_to_dict(view: SpecialistView) -> dict:
    specialist = view.specialist
    return {
        "specialist_id": specialist.specialist_id,
        "name": specialist.name,
        "email": specialist.email,
        "skills": view.skills,
        "capacity": specialist.capacity,
        "current_workload": specialist.current_workload,
        "availability": specialist.availability,
        "active": specialist.active,
        "completed_assignments_30d": specialist.completed_assignments_30d,
        "sla_success_rate_30d": specialist.sla_success_rate_30d,
        "average_resolution_minutes_30d": specialist.average_resolution_minutes_30d,
        "assignment_acceptance_rate_30d": specialist.assignment_acceptance_rate_30d,
        "capacity_reliability_rate_30d": specialist.capacity_reliability_rate_30d,
        "effective_workload": view.effective_workload,
        "available_capacity": view.available_capacity,
        "operationally_available": view.operationally_available,
        "created_at": specialist.created_at,
        "updated_at": specialist.updated_at,
    }


def specialist_view_to_legacy_dict(view: SpecialistView) -> dict:
    specialist = view.specialist
    return {
        "specialistId": specialist.specialist_id,
        "name": specialist.name,
        "skills": view.skills,
        "accessPermissions": [],
        "maximumConcurrentAssignments": specialist.capacity,
        "currentAssignmentCount": specialist.current_workload,
        "effectiveWorkload": view.effective_workload,
        "availableCapacity": view.available_capacity,
        "operationallyAvailable": view.operationally_available,
        "completedAssignments30d": specialist.completed_assignments_30d,
        "slaSuccessRate30d": specialist.sla_success_rate_30d,
        "averageResolutionMinutes30d": specialist.average_resolution_minutes_30d,
        "assignmentAcceptanceRate30d": specialist.assignment_acceptance_rate_30d,
        "capacityReliabilityRate30d": specialist.capacity_reliability_rate_30d,
        "created_at": specialist.created_at,
        "updated_at": specialist.updated_at,
    }


def workload_view_to_dict(view: WorkloadView) -> dict:
    return {
        "specialist_id": view.specialist.specialist_id,
        "assigned_count": view.assigned_count,
        "tentative_reservation_count": view.tentative_reservation_count,
        "confirmed_reservation_count": view.confirmed_reservation_count,
        "available_capacity": view.available_capacity,
        "utilisation_percentage": view.utilisation_percentage,
        "updated_at": view.specialist.updated_at,
    }


async def set_specialist_availability_for_simulation(
    session: AsyncSession,
    specialist_id: str,
    payload: WorkforceSimulationAvailabilityRequest,
) -> SpecialistView:
    view = await get_specialist(session, specialist_id)
    specialist = view.specialist
    if specialist.availability == payload.availability:
        return view

    specialist.availability = payload.availability
    specialist.updated_at = datetime.now(timezone.utc)
    try:
        session.add(specialist)
        await session.commit()
        await session.refresh(specialist)
        return await get_specialist(session, specialist.specialist_id)
    except SQLAlchemyError as exc:
        await session.rollback()
        raise _database_error() from exc
