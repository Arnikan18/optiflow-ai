from dataclasses import dataclass
from datetime import datetime, timezone
from math import ceil
from typing import Optional

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import AssignmentRequest, Notification
from app.schemas.requests import (
    NotificationCreateRequest,
    normalize_channel,
    normalize_datetime,
    normalize_notification_id,
    normalize_notification_status,
    normalize_request_id,
    normalize_search,
)
from app.services import delivery_service
from app.services.assignment_service import CommunicationError


@dataclass(frozen=True)
class NotificationCreateResult:
    notification: Notification
    created: bool


@dataclass(frozen=True)
class NotificationListResult:
    notifications: list[Notification]
    page: int
    page_size: int
    total_items: int
    total_pages: int


def _database_error() -> CommunicationError:
    return CommunicationError(503, "COMMUNICATION_503", "Communication database operation failed")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _payload_matches(notification: Notification, payload: NotificationCreateRequest) -> bool:
    return (
        notification.notification_id == payload.notification_id
        and notification.recipient == payload.recipient
        and notification.channel == payload.channel
        and notification.subject == payload.subject
        and notification.message == payload.message
        and notification.related_request_id == payload.related_request_id
    )


async def _validate_related_request(session: AsyncSession, related_request_id: str | None) -> None:
    if related_request_id is None:
        return
    result = await session.execute(select(AssignmentRequest.id).where(AssignmentRequest.request_id == related_request_id))
    if result.scalar_one_or_none() is None:
        raise CommunicationError(404, "COMMUNICATION_404", "Related assignment request not found")


async def create_notification(session: AsyncSession, payload: NotificationCreateRequest) -> NotificationCreateResult:
    now_utc = _utc_now()
    try:
        if payload.idempotency_key:
            existing_by_key = await session.execute(
                select(Notification).where(Notification.idempotency_key == payload.idempotency_key)
            )
            existing_notification = existing_by_key.scalar_one_or_none()
            if existing_notification is not None:
                if not _payload_matches(existing_notification, payload):
                    raise CommunicationError(409, "COMMUNICATION_409", "Idempotency key was used with a different payload")
                return NotificationCreateResult(existing_notification, created=False)

        duplicate_id = await session.execute(select(Notification.id).where(Notification.notification_id == payload.notification_id))
        if duplicate_id.scalar_one_or_none() is not None:
            raise CommunicationError(409, "COMMUNICATION_409", "Notification identifier already exists")

        await _validate_related_request(session, payload.related_request_id)

        notification = Notification(
            notification_id=payload.notification_id,
            recipient=payload.recipient,
            channel=payload.channel,
            subject=payload.subject,
            message=payload.message,
            status="PENDING",
            idempotency_key=payload.idempotency_key,
            related_request_id=payload.related_request_id,
            created_at=now_utc,
            attempt_count=0,
            updated_at=now_utc,
        )
        session.add(notification)

        delivery = delivery_service.simulate_delivery(
            notification_id=notification.notification_id,
            recipient=notification.recipient,
            channel=notification.channel,
        )
        attempted_at = _utc_now()
        notification.attempt_count += 1
        notification.attempted_at = attempted_at
        notification.updated_at = attempted_at
        if delivery.success:
            notification.status = "DELIVERED"
            notification.delivered_at = attempted_at
            notification.failure_reason = None
        else:
            notification.status = "FAILED"
            notification.delivered_at = None
            notification.failure_reason = delivery.failure_reason or "Simulated delivery failed"

        await session.commit()
        await session.refresh(notification)
        return NotificationCreateResult(notification, created=True)
    except CommunicationError:
        await session.rollback()
        raise
    except IntegrityError as exc:
        await session.rollback()
        raise CommunicationError(409, "COMMUNICATION_409", "Notification conflict") from exc
    except SQLAlchemyError as exc:
        await session.rollback()
        raise _database_error() from exc
    except Exception as exc:
        await session.rollback()
        raise CommunicationError(500, "COMMUNICATION_500", "Notification delivery simulation failed") from exc


async def create_legacy_notification(
    session: AsyncSession,
    *,
    recipient_id: str,
    notification_type: str,
    message: str,
    idempotency_key: str | None,
) -> NotificationCreateResult:
    raw_notification_id = idempotency_key.strip() if idempotency_key else f"NOT-{recipient_id}-{notification_type}"
    if not raw_notification_id or len(raw_notification_id) > 64:
        raise CommunicationError(422, "COMMUNICATION_422", "idempotencyKey must produce a notification identifier")
    normalized_type = notification_type.strip().upper()
    if "EMAIL" in normalized_type or "@" in recipient_id:
        channel = "EMAIL"
        subject = "OptiFlow notification"
    elif "SMS" in normalized_type:
        channel = "SMS"
        subject = None
    elif "WEBHOOK" in normalized_type:
        channel = "WEBHOOK"
        subject = "OptiFlow notification"
    else:
        channel = "IN_APP"
        subject = "OptiFlow notification"

    payload = NotificationCreateRequest(
        notification_id=raw_notification_id,
        recipient=recipient_id,
        channel=channel,
        subject=subject,
        message=message,
        idempotency_key=idempotency_key.strip() if idempotency_key else None,
    )
    return await create_notification(session, payload)


async def list_notifications(
    session: AsyncSession,
    *,
    page: int,
    page_size: int,
    status: Optional[str] = None,
    channel: Optional[str] = None,
    recipient: Optional[str] = None,
    related_request_id: Optional[str] = None,
    created_after: Optional[datetime] = None,
    created_before: Optional[datetime] = None,
    search: Optional[str] = None,
) -> NotificationListResult:
    try:
        conditions = []
        if status is not None:
            conditions.append(Notification.status == normalize_notification_status(status))
        if channel is not None:
            conditions.append(Notification.channel == normalize_channel(channel))
        if recipient is not None and recipient.strip():
            conditions.append(Notification.recipient.ilike(f"%{recipient.strip()}%"))
        if related_request_id is not None:
            conditions.append(Notification.related_request_id == normalize_request_id(related_request_id))
        created_after = normalize_datetime(created_after, "created_after")
        created_before = normalize_datetime(created_before, "created_before")
        if created_after and created_before and created_after > created_before:
            raise CommunicationError(422, "COMMUNICATION_422", "created_after cannot be later than created_before")
        if created_after is not None:
            conditions.append(Notification.created_at >= created_after)
        if created_before is not None:
            conditions.append(Notification.created_at <= created_before)

        normalized_search = normalize_search(search)
        if normalized_search:
            pattern = f"%{normalized_search}%"
            conditions.append(
                or_(
                    Notification.notification_id.ilike(pattern),
                    Notification.recipient.ilike(pattern),
                    Notification.subject.ilike(pattern),
                    Notification.message.ilike(pattern),
                )
            )

        total_result = await session.execute(select(func.count(Notification.id)).where(*conditions))
        total_items = total_result.scalar_one() or 0
        total_pages = ceil(total_items / page_size) if total_items else 0
        result = await session.execute(
            select(Notification)
            .where(*conditions)
            .order_by(Notification.created_at.desc(), Notification.notification_id.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        notifications = list(result.scalars().all())
        return NotificationListResult(
            notifications=notifications,
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


async def get_notification(session: AsyncSession, notification_id: str) -> Notification:
    try:
        normalized_id = normalize_notification_id(notification_id)
    except ValueError as exc:
        raise CommunicationError(422, "COMMUNICATION_422", str(exc)) from exc

    try:
        result = await session.execute(select(Notification).where(Notification.notification_id == normalized_id))
        notification = result.scalar_one_or_none()
        if notification is None:
            raise CommunicationError(404, "COMMUNICATION_404", "Notification not found")
        return notification
    except CommunicationError:
        raise
    except SQLAlchemyError as exc:
        await session.rollback()
        raise _database_error() from exc


def notification_to_legacy_dict(notification: Notification) -> dict:
    return {
        "notificationId": notification.notification_id,
        "recipientType": notification.channel,
        "recipientId": notification.recipient,
        "message": notification.message,
        "deliveryStatus": notification.status,
        "deliveredAt": notification.delivered_at,
    }
