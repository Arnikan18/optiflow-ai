import json
import os
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.models import Specialist, SpecialistSkill, SpecialistAccess, AvailabilitySlot, WorkloadRecord, Reservation, FailureMode

async def seed_database(session: AsyncSession):
    scenario_path = "/app/scenarios/phase2-demo.json"
    if not os.path.exists(scenario_path):
        scenario_path = os.path.join(os.path.dirname(__file__), "../../../../scenarios/phase2-demo.json")
        
    with open(scenario_path, "r") as f:
        data = json.load(f)
        
    # Clear existing
    await session.execute(Specialist.__table__.delete())
    await session.execute(SpecialistSkill.__table__.delete())
    await session.execute(SpecialistAccess.__table__.delete())
    await session.execute(AvailabilitySlot.__table__.delete())
    await session.execute(WorkloadRecord.__table__.delete())
    await session.execute(Reservation.__table__.delete())
    await session.execute(FailureMode.__table__.delete())
    
    # Insert specialists
    for spec in data["workforce"]["specialists"]:
        session.add(Specialist(**spec))
        
    # Insert skills
    for sk in data["workforce"]["skills"]:
        session.add(SpecialistSkill(**sk))
        
    # Insert access
    for acc in data["workforce"]["accessPermissions"]:
        session.add(SpecialistAccess(**acc))
        
    # Insert slots
    for slot in data["workforce"]["availability"]:
        session.add(AvailabilitySlot(**slot))
        
    # Insert workloads
    for wl in data["workforce"]["workloads"]:
        session.add(WorkloadRecord(**wl))
        
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
