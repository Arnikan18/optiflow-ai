import asyncio
import logging
from fastapi import FastAPI, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import text

from app.config.settings import settings
from app.adapters.tool_client import ToolClient

logger = logging.getLogger("core-api.main")

from app.database.session import async_session, engine

async def get_db():
    async with async_session() as session:
        yield session
        await session.commit()

# Application Lifespan
import contextlib
@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await engine.dispose()

app = FastAPI(
    title="OptiFlow Core API",
    version="4.0",
    lifespan=lifespan
)

@app.get("/health")
async def health() -> dict[str, str]:
    """Basic health check verifying FastAPI process viability."""
    return {
        "service": "core-api",
        "status": "UP",
        "version": "4.0"
    }

# Helper health checker using direct httpx request
async def verify_health_status(tool_client: ToolClient, service_name: str, base_url: str) -> str:
    import httpx
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            response = await client.get(f"{base_url}/health")
            if response.status_code == 200:
                return "UP"
        return "DOWN"
    except Exception:
        return "DOWN"


async def execute_health_aggregation(db: AsyncSession) -> dict:
    # Check PostgreSQL
    db_status = "DOWN"
    try:
        await db.execute(text("SELECT 1"))
        db_status = "UP"
    except Exception:
        pass
        
    services = {
        "core": "UP",
        "postgres": db_status
    }
    
    # Ping tools concurrently via tool client
    client = ToolClient()
    tasks = [
        verify_health_status(client, "crm", settings.crm_service_url),
        verify_health_status(client, "incident", settings.incident_service_url),
        verify_health_status(client, "workforce", settings.workforce_service_url),
        verify_health_status(client, "communication", settings.communication_service_url)
    ]
    results = await asyncio.gather(*tasks)
    
    services["crm"] = results[0]
    services["incident"] = results[1]
    services["workforce"] = results[2]
    services["communication"] = results[3]
    
    all_ready = all(v == "UP" for v in services.values())
    return {
        "status": "READY" if all_ready else "DEGRADED",
        "services": services
    }

# GET /api/v1/system/health & legacy GET /api/system/health
@app.get("/api/v1/system/health")
async def system_health_v1(db: AsyncSession = Depends(get_db)):
    return await execute_health_aggregation(db)

@app.get("/api/system/health", deprecated=True)
async def system_health_legacy(db: AsyncSession = Depends(get_db)):
    return await execute_health_aggregation(db)


async def execute_portfolio_aggregation() -> dict:
    client = ToolClient()
    
    # Fetch customer list, incidents list, specialists list, and assignment requests list concurrently
    tasks = [
        client.get_customers(),
        client.get_incidents(),
        client.get_specialists(),
        client.get_assignment_requests()
    ]
    
    try:
        results = await asyncio.gather(*tasks)
        
        # Customers wrapper maps: {"customers": [...]}
        # Incidents wrapper maps: {"incidents": [...]}
        # Specialists wrapper maps: {"specialists": [...]}
        # Assignment requests wrapper maps: {"assignment_requests": [...]}
        customers_list = results[0].get("customers", []) if results[0] else []
        incidents_list = results[1].get("incidents", []) if results[1] else []
        specialists_list = results[2].get("specialists", []) if results[2] else []
        requests_list = results[3].get("assignment_requests", []) if results[3] else []
        
        return {
            "customers": customers_list,
            "escalations": incidents_list, # Map to 'escalations' for portfolio backward compatibility in React
            "specialists": specialists_list,
            "assignmentRequests": requests_list
        }
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to aggregate downstream portfolio data: {str(e)}"
        )

# GET /api/v1/demo/portfolio & legacy GET /api/demo/portfolio
@app.get("/api/v1/demo/portfolio")
async def get_demo_portfolio_v1():
    return await execute_portfolio_aggregation()

@app.get("/api/demo/portfolio", deprecated=True)
async def get_demo_portfolio_legacy():
    return await execute_portfolio_aggregation()


async def execute_system_reset() -> dict:
    client = ToolClient()
    
    # Trigger admin resets concurrently
    tasks = [
        client.reset_db(settings.crm_service_url),
        client.reset_db(settings.incident_service_url),
        client.reset_db(settings.workforce_service_url),
        client.reset_db(settings.communication_service_url)
    ]
    
    try:
        results = await asyncio.gather(*tasks, return_exceptions=True)
        errors = []
        for r, name in zip(results, ["crm", "incident", "workforce", "communication"]):
            if isinstance(r, Exception):
                errors.append(f"{name} reset failed: {str(r)}")
            elif r is None:
                errors.append(f"{name} reset returned no data")
                
        if errors:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Downstream reset failure: {'; '.join(errors)}"
            )
            
        return {"status": "success", "message": "All mock databases reset successfully"}
    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Reset exception: {str(e)}"
        )

# POST /api/v1/control-room/reset & legacy POST /api/control/reset
@app.post("/api/v1/control-room/reset")
async def control_reset_v1():
    return await execute_system_reset()

@app.post("/api/control/reset", deprecated=True)
async def control_reset_legacy():
    return await execute_system_reset()
