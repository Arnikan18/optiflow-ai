import json
import os
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.models import Customer, CommercialDependency, FailureMode

async def seed_database(session: AsyncSession):
    scenario_path = "/app/scenarios/phase2-demo.json"
    if not os.path.exists(scenario_path):
        scenario_path = os.path.join(os.path.dirname(__file__), "../../../../scenarios/phase2-demo.json")
        
    with open(scenario_path, "r") as f:
        data = json.load(f)
        
    # Clear existing
    await session.execute(Customer.__table__.delete())
    await session.execute(CommercialDependency.__table__.delete())
    await session.execute(FailureMode.__table__.delete())
    
    # Insert customers
    for cust in data["crm"]["customers"]:
        session.add(Customer(**cust))
        
    # Insert dependencies
    for dep in data["crm"]["commercialDependencies"]:
        session.add(CommercialDependency(**dep))
        
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
