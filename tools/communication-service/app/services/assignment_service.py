from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from math import ceil
from typing import Optional

from sqlalchemy import and_, func, or_, select, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database.models import AssignmentRequest, ConfiguredResponse, FailureMode
from app.database.seed import seed_database
from app.schemas.requests import (
    AssignmentRequestCreateRequest,
    AssignmentResponseRequest,
    normalize_assignment_status,
    normalize_datetime,
    normalize_incident_id,
    normalize_request_id,
    normalize_search,
    normalize_specialist_id,
)


_LAST_RESET_AT: str | None = None


class CommunicationError(Exception):
    def __init__(self, status_code: int, error_code: str, message: str) -> None:
        self.status_code = status_code
        self.error_code = error_code
        self.message = message
        super().__init__(message)


@dataclass(frozen=True)
class AssignmentRequestListResult:
    assignment_requests: list[AssignmentRequest]
    page: int
    page_size: int
    total_items: int
    total_pages: int


def _database_error() -> CommunicationError:
    return CommunicationError(503, "COMMUNICATION_503", "Communication database operation failed")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _utc_now_iso() -> str:
    return _utc_now().isoformat()


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _parse_iso_datetime(value: str | None) -> datetime | None:
    if value is None:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def _expires_at_from_seconds(seconds: int | None, now_utc: datetime) -> str | None:
    if seconds is None:
        return None
    return (now_utc + timedelta(seconds=seconds)).isoformat()


def is_expired(request: AssignmentRequest, now_utc: datetime | None = None) -> bool:
    now_utc = now_utc or _utc_now()
    return request.status == "PENDING" and now_utc >= _as_utc(request.expires_at)


async def expire_pending_assignment_requests(session: AsyncSession, now_utc: datetime | None = None) -> int:
    now_utc = now_utc or _utc_now()
    result = await session.execute(
        update(AssignmentRequest)
        .where(AssignmentRequest.status == "PENDING", AssignmentRequest.expires_at <= now_utc)
        .values(status="EXPIRED", updated_at=now_utc)
    )
    return int(result.rowcount or 0)


async def deactivate_expired_simulation_rules(session: AsyncSession, now_utc: datetime | None = None) -> None:
    now_utc = now_utc or _utc_now()
    now_iso = now_utc.isoformat()
    await session.execute(
        update(ConfiguredResponse)
        .where(ConfiguredResponse.active == 1, ConfiguredResponse.expires_at.is_not(None), ConfiguredResponse.expires_at <= now_iso)
        .values(active=0, updated_at=now_iso)
    )
    await session.execute(
        update(FailureMode)
        .where(FailureMode.enabled == 1, FailureMode.expires_at.is_not(None), FailureMode.expires_at <= now_iso)
        .values(enabled=0, updated_at=now_iso)
    )


def _validate_ttl(expires_in_seconds: int | None) -> int:
    settings = get_settings()
    ttl = expires_in_seconds if expires_in_seconds is not None else settings.assignment_request_ttl_seconds
    if ttl < settings.min_assignment_request_ttl_seconds or ttl > settings.max_assignment_request_ttl_seconds:
        raise CommunicationError(
            422,
            "COMMUNICATION_422",
            "expires_in_seconds must be between configured minimum and maximum",
        )
    return ttl


def _same_assignment_create_payload(existing: AssignmentRequest, payload: AssignmentRequestCreateRequest) -> bool:
    return (
        existing.request_id == payload.request_id
        and existing.run_id == payload.run_id
        and existing.incident_id == payload.incident_id
        and existing.specialist_id == payload.specialist_id
        and existing.reservation_id == payload.reservation_id
        and existing.message == payload.message
    )


async def create_assignment_request(session: AsyncSession, payload: AssignmentRequestCreateRequest) -> tuple[AssignmentRequest, bool]:
    now_utc = _utc_now()
    ttl = _validate_ttl(payload.expires_in_seconds)
    try:
        await expire_pending_assignment_requests(session, now_utc)

        if payload.idempotency_key:
            existing_by_key = await session.execute(
                select(AssignmentRequest).where(AssignmentRequest.idempotency_key == payload.idempotency_key)
            )
            existing = existing_by_key.scalar_one_or_none()
            if existing is not None:
                if not _same_assignment_create_payload(existing, payload):
                    raise CommunicationError(
                        409,
                        "COMMUNICATION_409",
                        "Idempotency key already used for a different assignment request",
                    )
                return existing, False

        duplicate = await session.execute(select(AssignmentRequest.id).where(AssignmentRequest.request_id == payload.request_id))
        if duplicate.scalar_one_or_none() is not None:
            raise CommunicationError(409, "COMMUNICATION_409", "Assignment request identifier already exists")

        request = AssignmentRequest(
            request_id=payload.request_id,
            run_id=payload.run_id,
            incident_id=payload.incident_id,
            specialist_id=payload.specialist_id,
            reservation_id=payload.reservation_id,
            message=payload.message,
            status="PENDING",
            idempotency_key=payload.idempotency_key,
            created_at=now_utc,
            expires_at=now_utc + timedelta(seconds=ttl),
            updated_at=now_utc,
        )
        session.add(request)
        await session.commit()
        await session.refresh(request)
        return request, True
    except CommunicationError:
        await session.rollback()
        raise
    except IntegrityError as exc:
        await session.rollback()
        raise CommunicationError(409, "COMMUNICATION_409", "Assignment request conflict") from exc
    except SQLAlchemyError as exc:
        await session.rollback()
        raise _database_error() from exc


async def create_legacy_assignment_request(
    session: AsyncSession,
    *,
    specialist_id: str,
    incident_id: str,
    message: str | None,
    idempotency_key: str | None,
    run_id: str | None = None,
    reservation_id: str | None = None,
) -> AssignmentRequest:
    normalized_specialist_id = normalize_specialist_id(specialist_id)
    normalized_incident_id = normalize_incident_id(incident_id)
    raw_request_id = idempotency_key.strip() if idempotency_key else f"AR-{normalized_incident_id}-{normalized_specialist_id}"
    if not raw_request_id or len(raw_request_id) > 64:
        raise CommunicationError(422, "COMMUNICATION_422", "idempotencyKey must produce a request identifier")
    payload = AssignmentRequestCreateRequest(
        request_id=raw_request_id,
        run_id=run_id,
        incident_id=normalized_incident_id,
        specialist_id=normalized_specialist_id,
        reservation_id=reservation_id,
        message=message or "Please review and respond to this incident assignment request.",
        idempotency_key=idempotency_key,
    )
    request, _ = await create_assignment_request(session, payload)
    return request


async def list_assignment_requests(
    session: AsyncSession,
    *,
    page: int,
    page_size: int,
    status: Optional[str] = None,
    incident_id: Optional[str] = None,
    specialist_id: Optional[str] = None,
    pending_only: bool = False,
    expired: Optional[bool] = None,
    created_after: Optional[datetime] = None,
    created_before: Optional[datetime] = None,
    search: Optional[str] = None,
) -> AssignmentRequestListResult:
    now_utc = _utc_now()
    try:
        await expire_pending_assignment_requests(session, now_utc)
        await session.commit()

        conditions = []
        if status is not None:
            conditions.append(AssignmentRequest.status == normalize_assignment_status(status))
        if incident_id is not None:
            conditions.append(AssignmentRequest.incident_id == normalize_incident_id(incident_id))
        if specialist_id is not None:
            conditions.append(AssignmentRequest.specialist_id == normalize_specialist_id(specialist_id))
        if pending_only:
            conditions.extend([AssignmentRequest.status == "PENDING", AssignmentRequest.expires_at > now_utc])
        if expired is True:
            conditions.append(AssignmentRequest.status == "EXPIRED")
        elif expired is False:
            conditions.append(AssignmentRequest.status != "EXPIRED")
        created_after = normalize_datetime(created_after, "created_after")
        created_before = normalize_datetime(created_before, "created_before")
        if created_after and created_before and created_after > created_before:
            raise CommunicationError(422, "COMMUNICATION_422", "created_after cannot be later than created_before")
        if created_after is not None:
            conditions.append(AssignmentRequest.created_at >= created_after)
        if created_before is not None:
            conditions.append(AssignmentRequest.created_at <= created_before)

        normalized_search = normalize_search(search)
        if normalized_search:
            pattern = f"%{normalized_search}%"
            conditions.append(
                or_(
                    AssignmentRequest.request_id.ilike(pattern),
                    AssignmentRequest.incident_id.ilike(pattern),
                    AssignmentRequest.specialist_id.ilike(pattern),
                    AssignmentRequest.message.ilike(pattern),
                )
            )

        total_result = await session.execute(select(func.count(AssignmentRequest.id)).where(*conditions))
        total_items = total_result.scalar_one() or 0
        total_pages = ceil(total_items / page_size) if total_items else 0
        result = await session.execute(
            select(AssignmentRequest)
            .where(*conditions)
            .order_by(AssignmentRequest.created_at.desc(), AssignmentRequest.request_id.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        requests = list(result.scalars().all())
        return AssignmentRequestListResult(
            assignment_requests=requests,
            page=page,
            page_size=page_size,
            total_items=total_items,
            total_pages=total_pages,
        )
    except ValueError as exc:
        raise CommunicationError(422, "COMMUNICATION_422", str(exc)) from exc
    except CommunicationError:
        raise
    except SQLAlchemyError as exc:
        await session.rollback()
        raise _database_error() from exc


async def _matching_configured_response(
    session: AsyncSession,
    request: AssignmentRequest,
    now_utc: datetime,
) -> ConfiguredResponse | None:
    await deactivate_expired_simulation_rules(session, now_utc)
    result = await session.execute(
        select(ConfiguredResponse)
        .where(
            ConfiguredResponse.active == 1,
            or_(ConfiguredResponse.specialist_id.is_(None), ConfiguredResponse.specialist_id == request.specialist_id),
            or_(ConfiguredResponse.incident_id.is_(None), ConfiguredResponse.incident_id == request.incident_id),
        )
        .order_by(
            ConfiguredResponse.incident_id.is_(None),
            ConfiguredResponse.specialist_id.is_(None),
            ConfiguredResponse.configuration_id.asc(),
        )
    )
    return result.scalars().first()


async def apply_configured_response_if_due(
    session: AsyncSession,
    request: AssignmentRequest,
    now_utc: datetime | None = None,
) -> AssignmentRequest:
    now_utc = now_utc or _utc_now()
    if request.status != "PENDING" or is_expired(request, now_utc):
        return request

    configured = await _matching_configured_response(session, request, now_utc)
    if configured is None:
        return request

    due_at = _as_utc(request.created_at) + timedelta(seconds=configured.delay_seconds or 0)
    if now_utc < due_at:
        return request

    request.status = configured.next_status
    request.response_note = configured.response_reason
    request.response_reason = configured.response_reason
    request.responded_at = now_utc
    request.updated_at = now_utc
    session.add(request)

    if configured.apply_once:
        configured.active = 0
        configured.consumed_at = now_utc.isoformat()
        configured.updated_at = now_utc.isoformat()
        session.add(configured)

    await session.commit()
    await session.refresh(request)
    return request


async def get_assignment_request(session: AsyncSession, request_id: str) -> AssignmentRequest:
    try:
        normalized_id = normalize_request_id(request_id)
    except ValueError as exc:
        raise CommunicationError(422, "COMMUNICATION_422", str(exc)) from exc

    try:
        result = await session.execute(select(AssignmentRequest).where(AssignmentRequest.request_id == normalized_id))
        request = result.scalar_one_or_none()
        if request is None:
            raise CommunicationError(404, "COMMUNICATION_404", "Assignment request not found")
        if is_expired(request):
            request.status = "EXPIRED"
            request.updated_at = _utc_now()
            session.add(request)
            await session.commit()
            await session.refresh(request)
            return request
        request = await apply_configured_response_if_due(session, request)
        return request
    except CommunicationError:
        raise
    except SQLAlchemyError as exc:
        await session.rollback()
        raise _database_error() from exc


async def respond_to_assignment_request(
    session: AsyncSession,
    request_id: str,
    payload: AssignmentResponseRequest,
) -> AssignmentRequest:
    now_utc = _utc_now()
    try:
        normalized_id = normalize_request_id(request_id)
        await expire_pending_assignment_requests(session, now_utc)
        result = await session.execute(select(AssignmentRequest).where(AssignmentRequest.request_id == normalized_id))
        request = result.scalar_one_or_none()
        if request is None:
            raise CommunicationError(404, "COMMUNICATION_404", "Assignment request not found")

        if request.status == payload.response:
            return request
        if request.status in ("ACCEPTED", "REJECTED"):
            raise CommunicationError(409, "COMMUNICATION_409", "Assignment request already has a final response")
        if request.status in ("EXPIRED", "CANCELLED") or is_expired(request, now_utc):
            if is_expired(request, now_utc):
                request.status = "EXPIRED"
                request.updated_at = now_utc
                session.add(request)
                await session.commit()
            raise CommunicationError(409, "COMMUNICATION_409", "Assignment request cannot be answered")

        request.status = payload.response
        request.response_note = payload.response_note
        request.response_reason = payload.response_note
        request.responded_at = now_utc
        request.updated_at = now_utc
        session.add(request)
        await session.commit()
        await session.refresh(request)
        return request
    except ValueError as exc:
        await session.rollback()
        raise CommunicationError(422, "COMMUNICATION_422", str(exc)) from exc
    except CommunicationError:
        await session.rollback()
        raise
    except SQLAlchemyError as exc:
        await session.rollback()
        raise _database_error() from exc


async def reset_communication(session: AsyncSession) -> dict[str, int]:
    try:
        global _LAST_RESET_AT
        counts = await seed_database(session)
        _LAST_RESET_AT = _utc_now_iso()
        return counts
    except SQLAlchemyError as exc:
        await session.rollback()
        raise _database_error() from exc


async def configure_legacy_response(
    session: AsyncSession,
    *,
    specialist_id: str | None,
    incident_id: str | None = None,
    status: str,
    reason: str | None,
    delay_seconds: int = 0,
    delay_ms: int | None = None,
    apply_once: bool = True,
    expires_after_seconds: int | None = None,
) -> ConfiguredResponse:
    now_utc = _utc_now()
    now_iso = now_utc.isoformat()
    try:
        if delay_ms is not None:
            delay_seconds = int(delay_ms / 1000)

        configured = ConfiguredResponse(
            specialist_id=specialist_id,
            incident_id=incident_id,
            next_status=status,
            response_reason=reason,
            delay_seconds=delay_seconds,
            delay_ms=delay_ms or delay_seconds * 1000,
            apply_once=1 if apply_once else 0,
            active=1,
            created_at=now_iso,
            expires_at=_expires_at_from_seconds(expires_after_seconds, now_utc),
            updated_at=now_iso,
        )
        session.add(configured)
        await session.commit()
        await session.refresh(configured)
        return configured
    except SQLAlchemyError as exc:
        await session.rollback()
        raise _database_error() from exc


def assignment_to_legacy_dict(request: AssignmentRequest) -> dict:
    return {
        "requestId": request.request_id,
        "runId": request.run_id,
        "status": request.status,
        "specialistId": request.specialist_id,
        "escalationId": request.incident_id,
        "reservationId": request.reservation_id,
        "message": request.message,
        "responseReason": request.response_reason or request.response_note,
        "respondedAt": request.responded_at,
        "expiresAt": request.expires_at,
    }


async def get_failure_mode(session: AsyncSession) -> FailureMode:
    result = await session.execute(select(FailureMode).limit(1))
    mode = result.scalar_one_or_none()
    if mode is not None:
        return mode

    mode = FailureMode(
        mode="HTTP_ERROR",
        failure_type="HTTP_ERROR",
        enabled=0,
        status_code=503,
        delay_seconds=0,
        delay_ms=0,
        affected_endpoint=None,
        scope=None,
        apply_once=0,
        message=None,
        created_at=_utc_now_iso(),
        expires_at=None,
        remaining_failures=None,
        updated_at=_utc_now_iso(),
    )
    session.add(mode)
    await session.commit()
    await session.refresh(mode)
    return mode


async def configure_failure_mode(
    session: AsyncSession,
    *,
    enabled: bool,
    failure_type: str,
    status_code: int,
    delay_seconds: int,
    affected_endpoint: str | None,
    scope: str | None,
    apply_once: bool = False,
    expires_after_seconds: int | None = None,
    message: str | None = None,
) -> FailureMode:
    try:
        now_utc = _utc_now()
        now_iso = now_utc.isoformat()
        mode = await get_failure_mode(session)
        mode.enabled = 1 if enabled else 0
        mode.mode = failure_type
        mode.failure_type = failure_type
        mode.status_code = status_code
        mode.delay_seconds = delay_seconds
        mode.delay_ms = delay_seconds * 1000
        mode.affected_endpoint = affected_endpoint
        mode.scope = scope
        mode.apply_once = 1 if apply_once else 0
        mode.remaining_failures = 1 if enabled and apply_once else None
        mode.message = message
        if enabled:
            mode.created_at = now_iso
            mode.expires_at = _expires_at_from_seconds(expires_after_seconds, now_utc)
        else:
            mode.expires_at = None
        mode.updated_at = now_iso
        session.add(mode)
        await session.commit()
        await session.refresh(mode)
        return mode
    except SQLAlchemyError as exc:
        await session.rollback()
        raise _database_error() from exc


async def list_queued_response_rules(session: AsyncSession, active_only: bool = False) -> list[ConfiguredResponse]:
    now_utc = _utc_now()
    try:
        await deactivate_expired_simulation_rules(session, now_utc)
        stmt = select(ConfiguredResponse).order_by(ConfiguredResponse.configuration_id.asc())
        if active_only:
            stmt = stmt.where(ConfiguredResponse.active == 1)
        result = await session.execute(stmt)
        rules = list(result.scalars().all())
        await session.commit()
        return rules
    except SQLAlchemyError as exc:
        await session.rollback()
        raise _database_error() from exc


async def list_active_failure_modes(session: AsyncSession) -> list[FailureMode]:
    now_utc = _utc_now()
    try:
        await deactivate_expired_simulation_rules(session, now_utc)
        result = await session.execute(select(FailureMode).where(FailureMode.enabled == 1).order_by(FailureMode.mode_id.asc()))
        rules = list(result.scalars().all())
        await session.commit()
        return rules
    except SQLAlchemyError as exc:
        await session.rollback()
        raise _database_error() from exc


async def get_simulation_state(session: AsyncSession) -> dict[str, object]:
    now_utc = _utc_now()
    try:
        await deactivate_expired_simulation_rules(session, now_utc)
        await expire_pending_assignment_requests(session, now_utc)
        responses = await session.execute(select(ConfiguredResponse).order_by(ConfiguredResponse.configuration_id.asc()))
        failures = await session.execute(select(FailureMode).where(FailureMode.enabled == 1).order_by(FailureMode.mode_id.asc()))
        assignments = await session.execute(
            select(AssignmentRequest)
            .where(AssignmentRequest.status == "PENDING", AssignmentRequest.expires_at > now_utc)
            .order_by(AssignmentRequest.created_at.asc(), AssignmentRequest.request_id.asc())
        )
        response_rules = list(responses.scalars().all())
        failure_rules = list(failures.scalars().all())
        pending_assignments = list(assignments.scalars().all())
        await session.commit()
        return {
            "queued_specialist_responses": response_rules,
            "active_failure_modes": failure_rules,
            "pending_assignment_requests": pending_assignments,
            "last_reset_at": _LAST_RESET_AT,
            "demo_seed_status": "SEEDED",
        }
    except SQLAlchemyError as exc:
        await session.rollback()
        raise _database_error() from exc
