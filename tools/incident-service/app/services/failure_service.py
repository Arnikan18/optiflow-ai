import asyncio
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException, status
from app.database.models import FailureMode

async def apply_failure_mode(session: AsyncSession):
    stmt = select(FailureMode).where(FailureMode.enabled == 1)
    result = await session.execute(stmt)
    fm = result.scalar_one_or_none()
    
    if not fm:
        return
        
    if fm.remaining_failures is not None and fm.remaining_failures <= 0:
        return
        
    if fm.remaining_failures is not None:
        fm.remaining_failures -= 1
        fm.updated_at = datetime.now(timezone.utc).isoformat()
        session.add(fm)
        await session.commit()
        
    if fm.mode == "TIMEOUT":
        delay = (fm.delay_ms or 5000) / 1000.0
        await asyncio.sleep(delay)
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Gateway Timeout (Failure Mode Active)"
        )
    elif fm.mode == "HTTP_500":
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal Server Error (Failure Mode Active)"
        )
    elif fm.mode == "EMPTY_RESPONSE":
        raise HTTPException(
            status_code=status.HTTP_204_NO_CONTENT,
            detail=""
        )
