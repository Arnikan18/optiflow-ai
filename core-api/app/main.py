import httpx
import asyncio
import contextlib
from fastapi import FastAPI, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.sql import text
from typing import Dict, Any

from app.config.settings import settings

# Database session setup for Core
engine = create_async_engine(settings.database_url, echo=False)
async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

async def get_db():
    async with async_session() as session:
        yield session
        await session.commit()

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
    return {
        "service": "core-api",
        "status": "UP",
        "version": "4.0"
    }

async def fetch_tool_health(client: httpx.AsyncClient, name: str, url: str) -> str:
    try:
        # Pinging health endpoint
        response = await client.get(f"{url}/health", timeout=1.5)
        if response.status_code == 200:
            data = response.json()
            return data.get("status", "DOWN")
        return "DOWN"
    except Exception:
        return "DOWN"

@app.get("/api/system/health")
async def system_health(db: AsyncSession = Depends(get_db)):
    headers = {"X-Tool-Token": settings.tool_shared_token}
    
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
    
    # Ping tools concurrently
    async with httpx.AsyncClient(headers=headers) as client:
        tasks = [
            fetch_tool_health(client, "crm", settings.crm_service_url),
            fetch_tool_health(client, "incident", settings.incident_service_url),
            fetch_tool_health(client, "workforce", settings.workforce_service_url),
            fetch_tool_health(client, "communication", settings.communication_service_url)
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

async def fetch_tool_data(client: httpx.AsyncClient, url: str, path: str) -> Any:
    try:
        response = await client.get(f"{url}{path}", timeout=2.0)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        # Return fallback or raise
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Outage at downstream service {url}{path}: {str(e)}"
        )

@app.get("/api/demo/portfolio")
async def get_demo_portfolio():
    headers = {"X-Tool-Token": settings.tool_shared_token}
    
    async with httpx.AsyncClient(headers=headers) as client:
        # Fetch CRM customers, Incident active escalations, Workforce specialists, Communication assignment-requests
        tasks = [
            fetch_tool_data(client, settings.crm_service_url, "/customers"),
            fetch_tool_data(client, settings.incident_service_url, "/escalations/active"),
            fetch_tool_data(client, settings.workforce_service_url, "/specialists"),
            fetch_tool_data(client, settings.communication_service_url, "/assignment-requests")
        ]
        
        try:
            results = await asyncio.gather(*tasks)
            return {
                "customers": results[0],
                "escalations": results[1],
                "specialists": results[2],
                "assignmentRequests": results[3]
            }
        except HTTPException as he:
            raise he
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to fetch portfolio: {str(e)}"
            )

@app.post("/api/control/reset")
async def control_reset():
    headers = {"X-Tool-Token": settings.tool_shared_token}
    
    async with httpx.AsyncClient(headers=headers) as client:
        tasks = [
            client.post(f"{settings.crm_service_url}/admin/reset"),
            client.post(f"{settings.incident_service_url}/admin/reset"),
            client.post(f"{settings.workforce_service_url}/admin/reset"),
            client.post(f"{settings.communication_service_url}/admin/reset")
        ]
        results = await asyncio.gather(*tasks)
        
        errors = []
        for r, name in zip(results, ["crm", "incident", "workforce", "communication"]):
            if r.status_code != 200:
                errors.append(f"{name} reset failed: {r.status_code}")
                
        if errors:
            raise HTTPException(status_code=502, detail="; ".join(errors))
            
    return {"status": "success", "message": "All mock databases reset successfully"}
