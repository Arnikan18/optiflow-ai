import json
import os
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.models import AssignmentRequest, Notification, ConfiguredResponse, FailureMode

async def seed_database(session: AsyncSession):
    scenario_path = "/app/scenarios/phase2-demo.json"
    if not os.path.exists(scenario_path):
        scenario_path = os.path.join(os.path.dirname(__file__), "../../../../scenarios/phase2-demo.json")
        
    with open(scenario_path, "r") as f:
        data = json.load(f)
        
    # Clear existing
    await session.execute(AssignmentRequest.__table__.delete())
    await session.execute(Notification.__table__.delete())
    await session.execute(ConfiguredResponse.__table__.delete())
    await session.execute(FailureMode.__table__.delete())
    
    # Insert responses
    for resp in data["communication"]["configuredResponses"]:
        session.add(ConfiguredResponse(**resp))
        
    # Insert default failure mode
    fm = FailureMode(
        mode="TIMEOUT",
        enabled=0,
        delay_ms=5000,
        remaining_failures=0,
        updated_at=datetime.now(timezone.utc).isoformat()
    )
    session.add(fm)
    
    await session.commit()
