from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from math import ceil
from typing import Optional

from sqlalchemy import func, or_, select, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database.models import AssignmentRequest, ConfiguredResponse
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


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


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


async def create_assignment_request(session: AsyncSession, payload: AssignmentRequestCreateRequest) -> AssignmentRequest:
    now_utc = _utc_now()
    ttl = _validate_ttl(payload.expires_in_seconds)
    try:
        duplicate = await session.execute(select(AssignmentRequest.id).where(AssignmentRequest.request_id == payload.request_id))
        if duplicate.scalar_one_or_none() is not None:
            raise CommunicationError(409, "COMMUNICATION_409", "Assignment request identifier already exists")

        request = AssignmentRequest(
            request_id=payload.request_id,
            incident_id=payload.incident_id,
            specialist_id=payload.specialist_id,
            message=payload.message,
            status="PENDING",
            created_at=now_utc,
            expires_at=now_utc + timedelta(seconds=ttl),
            updated_at=now_utc,
        )
        session.add(request)
        await session.commit()
        await session.refresh(request)
        return request
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
) -> AssignmentRequest:
    normalized_specialist_id = normalize_specialist_id(specialist_id)
    normalized_incident_id = normalize_incident_id(incident_id)
    raw_request_id = idempotency_key.strip() if idempotency_key else f"AR-{normalized_incident_id}-{normalized_specialist_id}"
    if not raw_request_id or len(raw_request_id) > 64:
        raise CommunicationError(422, "COMMUNICATION_422", "idempotencyKey must produce a request identifier")
    payload = AssignmentRequestCreateRequest(
        request_id=raw_request_id,
        incident_id=normalized_incident_id,
        specialist_id=normalized_specialist_id,
        message=message or "Please review and respond to this incident assignment request.",
    )
    return await create_assignment_request(session, payload)


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
        counts = await seed_database(session)
        return counts
    except SQLAlchemyError as exc:
        await session.rollback()
        raise _database_error() from exc


async def configure_legacy_response(
    session: AsyncSession,
    *,
    specialist_id: str | None,
    status: str,
    reason: str | None,
    delay_ms: int,
) -> ConfiguredResponse:
    now_iso = _utc_now().isoformat()
    try:
        result = await session.execute(select(ConfiguredResponse).where(ConfiguredResponse.specialist_id == specialist_id))
        configured = result.scalar_one_or_none()
        if configured is None:
            configured = ConfiguredResponse(
                specialist_id=specialist_id,
                next_status=status,
                response_reason=reason,
                delay_ms=delay_ms,
                active=1,
                updated_at=now_iso,
            )
        configured.next_status = status
        configured.response_reason = reason
        configured.delay_ms = delay_ms
        configured.active = 1
        configured.updated_at = now_iso
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
        "status": request.status,
        "specialistId": request.specialist_id,
        "escalationId": request.incident_id,
        "message": request.message,
        "responseReason": request.response_note,
        "respondedAt": request.responded_at,
        "expiresAt": request.expires_at,
    }
