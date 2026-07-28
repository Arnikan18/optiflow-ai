import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException, status
from app.database.models import FailureMode

async def apply_failure_mode(session: AsyncSession, endpoint_name: str | None = None):
    stmt = select(FailureMode).where(FailureMode.enabled == 1)
    result = await session.execute(stmt)
    fm = result.scalar_one_or_none()
    
    if not fm:
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

    delay_seconds = fm.delay_seconds
    if delay_seconds is None and fm.delay_ms is not None:
        delay_seconds = fm.delay_ms / 1000.0
    if delay_seconds:
        await asyncio.sleep(float(delay_seconds))

    failure_type = (fm.failure_type or fm.mode or "HTTP_ERROR").upper()
    if failure_type == "TIMEOUT":
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Gateway Timeout (Failure Mode Active)"
        )

    raise HTTPException(
        status_code=fm.status_code or status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="Communication failure mode active",
    )
