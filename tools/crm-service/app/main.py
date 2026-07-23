import os
import contextlib
from fastapi import FastAPI, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timezone

from app.config import settings
from app.database.session import get_db, engine
from app.database.base import Base
from app.database.models import Customer, CommercialDependency, FailureMode
from app.database.seed import seed_database
from app.middleware.authentication import verify_tool_token
from app.middleware.request_context import RequestContextMiddleware
from app.services.failure_service import apply_failure_mode

@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize DB schema
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    # Seed DB
    async with AsyncSession(engine) as session:
        await seed_database(session)
    yield
    await engine.dispose()

app = FastAPI(
    title="OptiFlow CRM Service Mock",
    version="4.0",
    lifespan=lifespan
)

# Register request tracking middleware
app.add_middleware(RequestContextMiddleware)

@app.get("/health")
async def health(db: AsyncSession = Depends(get_db)):
    try:
        # Verify db connectivity
        await db.execute(select(Customer).limit(1))
        return {
            "service": settings.service_name,
            "status": "UP",
            "database": "UP",
            "scenarioId": settings.scenario_id,
            "version": "4.0"
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Database unreachable: {str(e)}"
        )

# CRM APIs (require verification token except for health and docs)
@app.get("/customers", dependencies=[Depends(verify_tool_token)])
async def get_customers(db: AsyncSession = Depends(get_db)):
    await apply_failure_mode(db)
    result = await db.execute(select(Customer))
    customers = result.scalars().all()
    return customers

@app.get("/customers/{customer_id}", dependencies=[Depends(verify_tool_token)])
async def get_customer(customer_id: str, db: AsyncSession = Depends(get_db)):
    await apply_failure_mode(db)
    result = await db.execute(select(Customer).where(Customer.customer_id == customer_id))
    customer = result.scalar_one_or_none()
    if not customer:
        raise HTTPException(status_code=404, detail=f"Customer {customer_id} not found")
    return customer

@app.get("/customers/{customer_id}/commercial-context", dependencies=[Depends(verify_tool_token)])
async def get_commercial_context(customer_id: str, db: AsyncSession = Depends(get_db)):
    await apply_failure_mode(db)
    # Customer basic info
    result = await db.execute(select(Customer).where(Customer.customer_id == customer_id))
    customer = result.scalar_one_or_none()
    if not customer:
        raise HTTPException(status_code=404, detail=f"Customer {customer_id} not found")
    
    # Customer dependencies
    dep_result = await db.execute(select(CommercialDependency).where(CommercialDependency.customer_id == customer_id))
    dependencies = dep_result.scalars().all()
    
    # Envelope structure from spec (page 18)
    return {
        "customerId": customer.customer_id,
        "name": customer.name,
        "tier": customer.tier,
        "annualRecurringRevenue": customer.annual_recurring_revenue,
        "renewalDate": customer.renewal_date,
        "strategicAccount": bool(customer.strategic_account),
        "commercialDependencies": [
            {
                "type": dep.dependency_type,
                "description": dep.description,
                "impactLevel": dep.impact_level
            } for dep in dependencies
        ],
        "sourceUpdatedAt": customer.updated_at
    }

@app.get("/renewals", dependencies=[Depends(verify_tool_token)])
async def get_renewals(within_days: int = Query(default=30), db: AsyncSession = Depends(get_db)):
    await apply_failure_mode(db)
    # Return customers whose renewal_date is within next X days
    result = await db.execute(select(Customer))
    customers = result.scalars().all()
    
    close_renewals = []
    now = datetime.now(timezone.utc)
    for cust in customers:
        if cust.renewal_date:
            try:
                ren_date = datetime.fromisoformat(cust.renewal_date.replace("Z", "+00:00"))
                delta = (ren_date - now).days
                if 0 <= delta <= within_days:
                    close_renewals.append(cust)
            except ValueError:
                pass
    return close_renewals

# Admin routes
@app.post("/admin/customers/{customer_id}/update", dependencies=[Depends(verify_tool_token)])
async def update_customer(customer_id: str, data: dict, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Customer).where(Customer.customer_id == customer_id))
    customer = result.scalar_one_or_none()
    if not customer:
        raise HTTPException(status_code=404, detail=f"Customer {customer_id} not found")
        
    for k, v in data.items():
        if hasattr(customer, k):
            setattr(customer, k, v)
            
    customer.updated_at = datetime.now(timezone.utc).isoformat()
    db.add(customer)
    await db.commit()
    return {"status": "success", "customer_id": customer_id}

@app.post("/admin/failure-mode", dependencies=[Depends(verify_tool_token)])
async def configure_failure_mode(data: dict, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(FailureMode).limit(1))
    fm = result.scalar_one_or_none()
    if not fm:
        fm = FailureMode(mode=data.get("mode", "TIMEOUT"), enabled=0, updated_at="")
        
    fm.mode = data.get("mode", "TIMEOUT")
    fm.enabled = 1 if data.get("enabled", False) else 0
    fm.delay_ms = data.get("delayMs", 5000)
    fm.remaining_failures = data.get("failureCount", 2)
    fm.updated_at = datetime.now(timezone.utc).isoformat()
    
    db.add(fm)
    await db.commit()
    return {"status": "success", "mode": fm.mode, "enabled": bool(fm.enabled)}

@app.post("/admin/reset", dependencies=[Depends(verify_tool_token)])
async def admin_reset(db: AsyncSession = Depends(get_db)):
    await seed_database(db)
    return {"status": "success", "message": "Database reset to seed state"}
