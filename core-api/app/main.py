import asyncio
import logging
from datetime import datetime
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
    from app.database.models import Base
    from app.llm_settings.service import llm_settings_service

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with async_session() as session:
        await llm_settings_service.load(session)
    yield
    await engine.dispose()

app = FastAPI(
    title="OptiFlow Core API",
    version="4.0",
    lifespan=lifespan
)

from app.demo.routes import legacy_router as demo_legacy_router
from app.demo.routes import router as demo_router
from app.execution.routes import router as execution_router
from app.llm_settings.routes import router as llm_settings_router

app.include_router(demo_router)
app.include_router(demo_legacy_router)
app.include_router(execution_router)
app.include_router(llm_settings_router)

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


# --- AGENT RUN CONTROL ROUTING ---
import uuid
from pydantic import BaseModel
from typing import Optional, Dict, Any
from app.agent.manager import start_new_run, resume_run_from_checkpoint, load_last_checkpoint

from pydantic import field_validator

class CreateRunRequest(BaseModel):
    goal_text: str
    
    @field_validator("goal_text")
    @classmethod
    def validate_goal_text(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("goal_text cannot be empty or consist only of whitespace.")
        return v

class ApproveRunRequest(BaseModel):
    approval_status: str
    recommended_plan: Optional[Dict[str, Any]] = None

class ClarifyRunRequest(BaseModel):
    clarification_reply: str

@app.post("/api/v1/runs", status_code=status.HTTP_201_CREATED)
async def create_run(body: CreateRunRequest, db: AsyncSession = Depends(get_db)):
    run_id = f"RUN-{uuid.uuid4().hex[:8].upper()}"
    await start_new_run(run_id, body.goal_text)
    return {"run_id": run_id, "status": "RECEIVED"}

@app.get("/api/v1/runs/{run_id}")
async def get_run_status(run_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(
        text("SELECT run_id, status, current_node, recommended_plan_id FROM agent_runs WHERE run_id = :r"),
        {"r": run_id}
    )
    row = res.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Run not found")
        
    checkpoint = await load_last_checkpoint(run_id) or {}
    candidate_plans = checkpoint.get("candidate_plans") or []
    
    # ── Populate Candidate Summaries dynamically ──────────────────────────────
    from app.services.candidate_comparison_builder import CandidateComparisonBuilder
    
    enterprise_state = checkpoint.get("enterprise_state") or {}
    customers = enterprise_state.get("customers", [])
    
    pers_rec = checkpoint.get("personalized_recommendation")
    rec_plan_id = pers_rec.get("candidate_plan_id") if pers_rec else row[3]
    pers_reason = pers_rec.get("reason") if pers_rec else None
    
    summaries = CandidateComparisonBuilder.build_summaries(
        plans=candidate_plans,
        customers=customers,
        recommended_plan_id=rec_plan_id,
        personalized_reason=pers_reason
    )
    
    return {
        "run_id": row[0],
        "status": row[1],
        "current_node": row[2],
        "recommended_plan_id": row[3],
        "candidate_plans": candidate_plans,
        "confidence_report": checkpoint.get("confidence_report"),
        "autonomy_risk_report": checkpoint.get("autonomy_risk_report"),
        "replan_count": checkpoint.get("replan_count", 0),
        "excluded_specialist_incidents": checkpoint.get("excluded_specialist_incidents", []),
        "structured_goal": checkpoint.get("structured_goal"),
        "selected_tools": checkpoint.get("selected_tools", []),
        "business_summary": checkpoint.get("business_summary"),
        "change_summary": checkpoint.get("change_summary"),
        "personalized_recommendation": pers_rec,
        "candidate_plan_summary": [s.model_dump(mode="json") for s in summaries]
    }

@app.post("/api/v1/runs/{run_id}/approve")
async def approve_run(run_id: str, body: ApproveRunRequest, db: AsyncSession = Depends(get_db)):
    res = await db.execute(
        text("SELECT status FROM agent_runs WHERE run_id = :r"),
        {"r": run_id}
    )
    row = res.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Run not found")
    if row[0] in ("COMPLETED", "FAILED", "CANCELLED"):
        raise HTTPException(status_code=400, detail=f"Cannot approve run in {row[0]} state.")
        
    success = await resume_run_from_checkpoint(run_id, body.approval_status, body.recommended_plan)
    if not success:
        raise HTTPException(status_code=404, detail="Run checkpoint not found")
    return {"status": "success", "message": f"Run resumed with status: {body.approval_status}"}

@app.post("/api/v1/runs/{run_id}/clarify")
async def clarify_run(run_id: str, body: ClarifyRunRequest, db: AsyncSession = Depends(get_db)):
    res = await db.execute(
        text("SELECT status FROM agent_runs WHERE run_id = :r"),
        {"r": run_id}
    )
    row = res.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Run not found")
    if row[0] in ("COMPLETED", "FAILED", "CANCELLED"):
        raise HTTPException(status_code=400, detail=f"Cannot clarify run in {row[0]} state.")
    if row[0] != "WAITING_FOR_CLARIFICATION":
        raise HTTPException(status_code=400, detail=f"Cannot clarify run in {row[0]} state. Run must be in WAITING_FOR_CLARIFICATION state.")
        
    success = await resume_run_from_checkpoint(
        run_id=run_id, 
        approval_status="APPROVED", 
        clarification_reply=body.clarification_reply
    )
    if not success:
        raise HTTPException(status_code=404, detail="Run checkpoint not found")
    return {"status": "success", "message": "Run resumed after clarification"}

@app.post("/api/v1/runs/{run_id}/cancel")
async def cancel_run(run_id: str, db: AsyncSession = Depends(get_db)):
    res = await db.execute(
        text("SELECT status FROM agent_runs WHERE run_id = :r"),
        {"r": run_id}
    )
    row = res.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Run not found")
    if row[0] in ("COMPLETED", "FAILED", "CANCELLED"):
        raise HTTPException(status_code=400, detail=f"Cannot cancel run in {row[0]} state.")
        
    await db.execute(
        text("UPDATE agent_runs SET status = 'CANCELLED', current_node = 'cancel' WHERE run_id = :r"),
        {"r": run_id}
    )
    from app.database.persistence import save_run_event
    await save_run_event(
        session=db,
        run_id=run_id,
        sequence_number=99,
        event_type="RUN_CANCELLED",
        source="cancel_run",
        summary="Run was manually cancelled by the manager.",
        state_version=1
    )
    await db.commit()
    return {"status": "success", "message": "Run cancelled successfully."}


# --- SERVER-SENT EVENTS (SSE) STREAMING ---
import json
from sse_starlette.sse import EventSourceResponse

@app.get("/api/v1/runs/{run_id}/stream")
async def run_events_stream(run_id: str):
    """Streams real-time agent run events for the given run_id using SSE."""
    
    async def event_generator():
        # 1. Fetch historical events from database to feed client history
        async with async_session() as session:
            res = await session.execute(
                text("SELECT sequence_number, event_type, source, summary, payload, state_version FROM run_events WHERE run_id = :r ORDER BY sequence_number"),
                {"r": run_id}
            )
            rows = res.fetchall()
            for r in rows:
                ev = {
                    "run_id": run_id,
                    "sequence_number": r[0],
                    "event_type": r[1],
                    "source": r[2],
                    "summary": r[3],
                    "payload": r[4],
                    "state_version": r[5]
                }
                yield {"event": "run_event", "data": json.dumps(ev)}
                
        # 2. Subscribe to active updates broker queue
        from app.agent.events import event_publisher
        queue = event_publisher.subscribe(run_id)
        try:
            while True:
                # Wait for next event published asynchronously
                event_data = await queue.get()
                yield {"event": "run_event", "data": json.dumps(event_data)}
                queue.task_done()
        except asyncio.CancelledError:
            # Clean up subscriber list when client disconnects
            event_publisher.unsubscribe(run_id, queue)
            raise
            
    return EventSourceResponse(event_generator())
