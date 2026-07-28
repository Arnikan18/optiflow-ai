import asyncio
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException, status
from app.database.models import FailureMode


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_iso_datetime(value: str | None):
    if value is None:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


async def apply_failure_mode(session: AsyncSession, endpoint_name: str | None = None):
    stmt = select(FailureMode).where(FailureMode.enabled == 1)
    result = await session.execute(stmt)
    fm = result.scalar_one_or_none()
    
    if not fm:
        return

    now_utc = datetime.now(timezone.utc)
    expires_at = _parse_iso_datetime(fm.expires_at)
    if expires_at is not None and now_utc >= expires_at:
        fm.enabled = 0
        fm.updated_at = _utc_now_iso()
        session.add(fm)
        await session.commit()
        return

    if endpoint_name and fm.affected_endpoint:
        configured = fm.affected_endpoint.strip().lower()
        if configured not in (endpoint_name.lower(), "all", "*"):
            return

    if endpoint_name and fm.scope:
        configured_scope = fm.scope.strip().lower()
        endpoint_scope = endpoint_name.split(":", 1)[0].lower()
        if configured_scope not in (endpoint_scope, "all", "*"):
            return

    if fm.remaining_failures is not None and fm.remaining_failures <= 0:
        fm.enabled = 0
        fm.updated_at = _utc_now_iso()
        session.add(fm)
        await session.commit()
        return

    delay_seconds = fm.delay_seconds
    if delay_seconds is None and fm.delay_ms is not None:
        delay_seconds = fm.delay_ms / 1000.0
    if delay_seconds:
        await asyncio.sleep(float(delay_seconds))

    failure_type = (fm.failure_type or fm.mode or "HTTP_ERROR").upper()
    if fm.apply_once or fm.remaining_failures is not None:
        if fm.remaining_failures is not None:
            fm.remaining_failures = max(fm.remaining_failures - 1, 0)
        if fm.apply_once or fm.remaining_failures == 0:
            fm.enabled = 0
        fm.updated_at = _utc_now_iso()
        session.add(fm)
        await session.commit()

    if failure_type == "DELAY":
        return

    if failure_type == "TIMEOUT":
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=fm.message or "Gateway Timeout (Failure Mode Active)"
        )
    if failure_type == "CONNECTION_FAILURE":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=fm.message or "Connection failure simulation active",
        )
    if failure_type == "INVALID_RESPONSE":
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=fm.message or "Invalid response simulation active",
        )

    raise HTTPException(
        status_code=fm.status_code or status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=fm.message or "Communication failure mode active",
    )
