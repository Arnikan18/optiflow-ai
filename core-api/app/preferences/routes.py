from datetime import datetime, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.main_dependencies import get_db
from app.preferences.service import PreferenceSummary, get_preference_summary


router = APIRouter(prefix="/api/v1/preferences", tags=["preferences"])


@router.get("/summary", response_model=dict[str, Any])
async def preference_summary(
    recent_limit: Annotated[int, Query(ge=1, le=20)] = 5,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    summary: PreferenceSummary = await get_preference_summary(db, recent_limit)
    return {
        "success": True,
        "message": "Preference memory loaded",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "data": summary.model_dump(mode="json"),
    }
