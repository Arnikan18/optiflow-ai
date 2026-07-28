from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, delete, func, or_, select, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database.models import Reservation, Specialist, SpecialistSkill
from app.database.seed import build_seed_reservations, build_seed_specialists, ensure_failure_mode
from app.schemas.requests import (
    ReservationCreateRequest,
    ReservationVerificationRequest,
    normalize_incident_id,
    normalize_reservation_id,
    normalize_specialist_id,
)
from app.services.specialist_service import WorkforceError


ACTIVE_RESERVATION_STATUSES = ("TENTATIVE", "CONFIRMED")


def _database_error() -> WorkforceError:
    return WorkforceError(503, "WORKFORCE_503", "Workforce database operation failed")


def is_expired(reservation: Reservation, now_utc: datetime | None = None) -> bool:
    now_utc = now_utc or datetime.now(timezone.utc)
    expires_at = reservation.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return reservation.status == "TENTATIVE" and now_utc >= expires_at.astimezone(timezone.utc)


async def expire_pending_reservations(session: AsyncSession, now_utc: datetime | None = None) -> int:
    now_utc = now_utc or datetime.now(timezone.utc)
    result = await session.execute(
        update(Reservation)
        .where(Reservation.status == "TENTATIVE", Reservation.expires_at <= now_utc)
        .values(status="EXPIRED", updated_at=now_utc)
    )
    return int(result.rowcount or 0)


async def _active_pending_count(session: AsyncSession, specialist_id: str, now_utc: datetime) -> int:
    result = await session.execute(
        select(func.count(Reservation.id)).where(
            Reservation.specialist_id == specialist_id,
            Reservation.status == "TENTATIVE",
            Reservation.expires_at > now_utc,
        )
    )
    return int(result.scalar_one() or 0)


async def _get_specialist_for_update(session: AsyncSession, specialist_id: str) -> Specialist:
    result = await session.execute(select(Specialist).where(Specialist.specialist_id == specialist_id))
    specialist = result.scalar_one_or_none()
    if specialist is None:
        raise WorkforceError(404, "WORKFORCE_404", "Specialist not found")
    return specialist


def _validate_ttl(expires_in_seconds: int | None) -> int:
    settings = get_settings()
    ttl = expires_in_seconds if expires_in_seconds is not None else settings.reservation_ttl_seconds
    if ttl < settings.min_reservation_ttl_seconds or ttl > settings.max_reservation_ttl_seconds:
        raise WorkforceError(
            422,
            "WORKFORCE_422",
            "expires_in_seconds must be between configured minimum and maximum",
        )
    return ttl


def _same_reservation_create_payload(existing: Reservation, payload: ReservationCreateRequest) -> bool:
    return (
        existing.reservation_id == payload.reservation_id
        and existing.run_id == payload.run_id
        and existing.specialist_id == payload.specialist_id
        and existing.incident_id == payload.incident_id
    )


async def create_reservation(session: AsyncSession, payload: ReservationCreateRequest) -> tuple[Reservation, bool]:
    now_utc = datetime.now(timezone.utc)
    ttl = _validate_ttl(payload.expires_in_seconds)
    try:
        await expire_pending_reservations(session, now_utc)

        if payload.idempotency_key:
            existing_by_key = await session.execute(
                select(Reservation).where(Reservation.idempotency_key == payload.idempotency_key)
            )
            existing = existing_by_key.scalar_one_or_none()
            if existing is not None:
                if not _same_reservation_create_payload(existing, payload):
                    raise WorkforceError(
                        409,
                        "WORKFORCE_409",
                        "Idempotency key already used for a different reservation",
                    )
                return existing, False

        duplicate_id = await session.execute(
            select(Reservation.id).where(Reservation.reservation_id == payload.reservation_id)
        )
        if duplicate_id.scalar_one_or_none() is not None:
            raise WorkforceError(409, "WORKFORCE_409", "Reservation identifier already exists")

        specialist = await _get_specialist_for_update(session, payload.specialist_id)
        if not specialist.active:
            raise WorkforceError(409, "WORKFORCE_409", "Specialist is inactive")
        if not specialist.availability:
            raise WorkforceError(409, "WORKFORCE_409", "Specialist is unavailable")

        active_duplicate = await session.execute(
            select(Reservation.id).where(
                Reservation.specialist_id == payload.specialist_id,
                Reservation.incident_id == payload.incident_id,
                or_(
                    Reservation.status == "CONFIRMED",
                    and_(Reservation.status == "TENTATIVE", Reservation.expires_at > now_utc),
                ),
            )
        )
        if active_duplicate.scalar_one_or_none() is not None:
            raise WorkforceError(409, "WORKFORCE_409", "Active reservation already exists for specialist and incident")

        active_pending = await _active_pending_count(session, specialist.specialist_id, now_utc)
        if specialist.current_workload + active_pending >= specialist.capacity:
            raise WorkforceError(409, "WORKFORCE_409", "Specialist has no available capacity")

        reservation = Reservation(
            reservation_id=payload.reservation_id,
            run_id=payload.run_id,
            specialist_id=payload.specialist_id,
            incident_id=payload.incident_id,
            status="TENTATIVE",
            idempotency_key=payload.idempotency_key,
            created_at=now_utc,
            expires_at=now_utc + timedelta(seconds=ttl),
            updated_at=now_utc,
        )
        session.add(reservation)
        await session.commit()
        await session.refresh(reservation)
        return reservation, True
    except WorkforceError:
        await session.rollback()
        raise
    except IntegrityError as exc:
        await session.rollback()
        raise WorkforceError(409, "WORKFORCE_409", "Reservation conflict") from exc
    except SQLAlchemyError as exc:
        await session.rollback()
        raise _database_error() from exc


async def get_reservation(session: AsyncSession, reservation_id: str) -> Reservation:
    try:
        normalized_id = normalize_reservation_id(reservation_id)
    except ValueError as exc:
        raise WorkforceError(422, "WORKFORCE_422", str(exc)) from exc

    try:
        result = await session.execute(select(Reservation).where(Reservation.reservation_id == normalized_id))
        reservation = result.scalar_one_or_none()
        if reservation is None:
            raise WorkforceError(404, "WORKFORCE_404", "Reservation not found")
        if is_expired(reservation):
            reservation.status = "EXPIRED"
            reservation.updated_at = datetime.now(timezone.utc)
            session.add(reservation)
            await session.commit()
            await session.refresh(reservation)
        return reservation
    except WorkforceError:
        raise
    except SQLAlchemyError as exc:
        await session.rollback()
        raise _database_error() from exc


async def verify_reservation(session: AsyncSession, payload: ReservationVerificationRequest) -> dict:
    checked_at = datetime.now(timezone.utc)
    expected_values = {
        "run_id": payload.expected_run_id,
        "incident_id": payload.expected_incident_id,
        "specialist_id": payload.expected_specialist_id,
        "status": payload.expected_status,
    }

    try:
        result = await session.execute(select(Reservation).where(Reservation.reservation_id == payload.reservation_id))
        reservation = result.scalar_one_or_none()
        if reservation is None:
            return {
                "verified": False,
                "result": "not_found",
                "reservation_id": payload.reservation_id,
                "expected_values": expected_values,
                "actual_values": None,
                "failed_checks": ["reservation_not_found"],
                "checked_at": checked_at,
                "current_status": None,
            }

        if is_expired(reservation, checked_at):
            reservation.status = "EXPIRED"
            reservation.updated_at = checked_at
            session.add(reservation)
            await session.commit()
            await session.refresh(reservation)

        actual_values = {
            "run_id": reservation.run_id,
            "incident_id": reservation.incident_id,
            "specialist_id": reservation.specialist_id,
            "status": reservation.status,
            "expires_at": reservation.expires_at,
            "cancelled_at": reservation.cancelled_at,
        }
        failed_checks: list[str] = []
        if reservation.run_id != payload.expected_run_id:
            failed_checks.append("run_id_mismatch")
        if reservation.incident_id != payload.expected_incident_id:
            failed_checks.append("incident_id_mismatch")
        if reservation.specialist_id != payload.expected_specialist_id:
            failed_checks.append("specialist_id_mismatch")
        if reservation.status != payload.expected_status:
            failed_checks.append("status_not_confirmed")
        if reservation.status == "EXPIRED":
            failed_checks.append("reservation_expired")
        if reservation.status == "CANCELLED":
            failed_checks.append("reservation_cancelled")

        if reservation.status == "TENTATIVE":
            result_status = "pending"
        elif reservation.status == "EXPIRED":
            result_status = "expired"
        elif reservation.status == "CANCELLED":
            result_status = "cancelled"
        elif failed_checks:
            result_status = "inconsistent"
        else:
            result_status = "verified"

        return {
            "verified": result_status == "verified",
            "result": result_status,
            "reservation_id": reservation.reservation_id,
            "expected_values": expected_values,
            "actual_values": actual_values,
            "failed_checks": failed_checks,
            "checked_at": checked_at,
            "current_status": reservation.status,
        }
    except SQLAlchemyError as exc:
        await session.rollback()
        raise _database_error() from exc


async def confirm_reservation(session: AsyncSession, reservation_id: str) -> Reservation:
    now_utc = datetime.now(timezone.utc)
    try:
        normalized_id = normalize_reservation_id(reservation_id)
        await expire_pending_reservations(session, now_utc)
        result = await session.execute(select(Reservation).where(Reservation.reservation_id == normalized_id))
        reservation = result.scalar_one_or_none()
        if reservation is None:
            raise WorkforceError(404, "WORKFORCE_404", "Reservation not found")

        if reservation.status == "CONFIRMED":
            return reservation
        if reservation.status in ("CANCELLED", "EXPIRED") or is_expired(reservation, now_utc):
            if is_expired(reservation, now_utc):
                reservation.status = "EXPIRED"
                reservation.updated_at = now_utc
                session.add(reservation)
                await session.commit()
            raise WorkforceError(409, "WORKFORCE_409", "Reservation cannot be confirmed")

        specialist = await _get_specialist_for_update(session, reservation.specialist_id)
        if not specialist.active:
            raise WorkforceError(409, "WORKFORCE_409", "Specialist is inactive")
        if not specialist.availability:
            raise WorkforceError(409, "WORKFORCE_409", "Specialist is unavailable")
        if specialist.current_workload >= specialist.capacity:
            raise WorkforceError(409, "WORKFORCE_409", "Specialist has no confirmed capacity")

        reservation.status = "CONFIRMED"
        reservation.confirmed_at = now_utc
        reservation.updated_at = now_utc
        specialist.current_workload += 1
        specialist.updated_at = now_utc
        session.add_all([reservation, specialist])
        await session.commit()
        await session.refresh(reservation)
        return reservation
    except ValueError as exc:
        await session.rollback()
        raise WorkforceError(422, "WORKFORCE_422", str(exc)) from exc
    except WorkforceError:
        await session.rollback()
        raise
    except SQLAlchemyError as exc:
        await session.rollback()
        raise _database_error() from exc


async def cancel_reservation(
    session: AsyncSession,
    reservation_id: str,
    cancellation_reason: str | None = None,
) -> Reservation:
    now_utc = datetime.now(timezone.utc)
    try:
        normalized_id = normalize_reservation_id(reservation_id)
        result = await session.execute(select(Reservation).where(Reservation.reservation_id == normalized_id))
        reservation = result.scalar_one_or_none()
        if reservation is None:
            raise WorkforceError(404, "WORKFORCE_404", "Reservation not found")

        if reservation.status == "TENTATIVE" and is_expired(reservation, now_utc):
            reservation.status = "EXPIRED"
            reservation.updated_at = now_utc
            session.add(reservation)
            await session.commit()
            await session.refresh(reservation)
            return reservation

        if reservation.status in ("CANCELLED", "EXPIRED"):
            return reservation

        if reservation.status == "CONFIRMED":
            specialist = await _get_specialist_for_update(session, reservation.specialist_id)
            specialist.current_workload = max(specialist.current_workload - 1, 0)
            specialist.updated_at = now_utc
            session.add(specialist)

        reservation.status = "CANCELLED"
        reservation.cancelled_at = now_utc
        if cancellation_reason:
            reservation.cancellation_reason = cancellation_reason
        reservation.updated_at = now_utc
        session.add(reservation)
        await session.commit()
        await session.refresh(reservation)
        return reservation
    except ValueError as exc:
        await session.rollback()
        raise WorkforceError(422, "WORKFORCE_422", str(exc)) from exc
    except WorkforceError:
        await session.rollback()
        raise
    except SQLAlchemyError as exc:
        await session.rollback()
        raise _database_error() from exc


async def reset_workforce(session: AsyncSession) -> dict[str, int]:
    try:
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
    except SQLAlchemyError as exc:
        await session.rollback()
        raise _database_error() from exc


async def create_legacy_tentative_reservation(
    session: AsyncSession,
    *,
    specialist_id: str,
    incident_id: str,
    reservation_id: str | None = None,
    run_id: str | None = None,
) -> Reservation:
    specialist_id = normalize_specialist_id(specialist_id)
    incident_id = normalize_incident_id(incident_id)
    reservation_id = normalize_reservation_id(reservation_id or f"RES-{specialist_id}-{incident_id}")
    payload = ReservationCreateRequest(
        reservation_id=reservation_id,
        run_id=run_id,
        idempotency_key=reservation_id,
        specialist_id=specialist_id,
        incident_id=incident_id,
    )
    reservation, _ = await create_reservation(session, payload)
    return reservation
