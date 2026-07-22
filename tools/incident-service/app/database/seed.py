import json
import os
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.models import Escalation, EscalationSkill, EscalationAccess, AssignmentHistory, IncidentEvent, FailureMode

async def seed_database(session: AsyncSession):
    scenario_path = "/app/scenarios/phase2-demo.json"
    if not os.path.exists(scenario_path):
        scenario_path = os.path.join(os.path.dirname(__file__), "../../../../scenarios/phase2-demo.json")
        
    with open(scenario_path, "r") as f:
        data = json.load(f)
        
    # Clear existing
    await session.execute(Escalation.__table__.delete())
    await session.execute(EscalationSkill.__table__.delete())
    await session.execute(EscalationAccess.__table__.delete())
    await session.execute(AssignmentHistory.__table__.delete())
    await session.execute(IncidentEvent.__table__.delete())
    await session.execute(FailureMode.__table__.delete())
    
    # Insert escalations
    for esc in data["incident"]["escalations"]:
        session.add(Escalation(**esc))
        
    # Insert skills
    for sk in data["incident"]["skills"]:
        session.add(EscalationSkill(**sk))
        
    # Insert access
    for acc in data["incident"]["accessRequirements"]:
        session.add(EscalationAccess(**acc))
        
    # Insert history
    for hist in data["incident"]["assignmentHistory"]:
        session.add(AssignmentHistory(**hist))
        
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
