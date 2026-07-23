import os
import contextlib
import random
from fastapi import FastAPI, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timezone

from app.config import settings
from app.database.session import get_db, engine
from app.database.base import Base
from app.database.models import Escalation, EscalationSkill, EscalationAccess, AssignmentHistory, FailureMode
from app.database.seed import seed_database
from app.middleware.authentication import verify_tool_token
from app.middleware.request_context import RequestContextMiddleware
from app.services.failure_service import apply_failure_mode

@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncSession(engine) as session:
        await seed_database(session)
    yield
    await engine.dispose()

app = FastAPI(
    title="OptiFlow Incident Service Mock",
    version="4.0",
    lifespan=lifespan
)

app.add_middleware(RequestContextMiddleware)

@app.get("/health")
async def health(db: AsyncSession = Depends(get_db)):
    try:
        await db.execute(select(Escalation).limit(1))
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

@app.get("/escalations", dependencies=[Depends(verify_tool_token)])
async def get_escalations(db: AsyncSession = Depends(get_db)):
    await apply_failure_mode(db)
    result = await db.execute(select(Escalation))
    return result.scalars().all()

@app.get("/escalations/active", dependencies=[Depends(verify_tool_token)])
async def get_active_escalations(db: AsyncSession = Depends(get_db)):
    await apply_failure_mode(db)
    result = await db.execute(select(Escalation).where(Escalation.status != "RESOLVED"))
    escalations = result.scalars().all()
    
    response_data = []
    for esc in escalations:
        # Get skills
        sk_res = await db.execute(select(EscalationSkill.skill_code).where(EscalationSkill.escalation_id == esc.escalation_id))
        skills = sk_res.scalars().all()
        
        # Get access
        acc_res = await db.execute(select(EscalationAccess.access_code).where(EscalationAccess.escalation_id == esc.escalation_id))
        access = acc_res.scalars().all()
        
        response_data.append({
            "escalationId": esc.escalation_id,
            "customerId": esc.customer_id,
            "title": esc.title,
            "severity": esc.severity,
            "slaDeadline": esc.sla_deadline,
            "status": esc.status,
            "requiredSkills": list(skills),
            "requiredAccess": list(access),
            "requiredDurationMinutes": esc.required_duration_minutes,
            "workaroundStatus": esc.workaround_status,
            "currentSpecialistId": esc.current_specialist_id,
            "sourceUpdatedAt": esc.updated_at
        })
        
    return response_data

@app.get("/escalations/{escalation_id}", dependencies=[Depends(verify_tool_token)])
async def get_escalation(escalation_id: str, db: AsyncSession = Depends(get_db)):
    await apply_failure_mode(db)
    result = await db.execute(select(Escalation).where(Escalation.escalation_id == escalation_id))
    esc = result.scalar_one_or_none()
    if not esc:
        raise HTTPException(status_code=404, detail=f"Escalation {escalation_id} not found")
        
    sk_res = await db.execute(select(EscalationSkill.skill_code).where(EscalationSkill.escalation_id == esc.escalation_id))
    skills = sk_res.scalars().all()
    
    acc_res = await db.execute(select(EscalationAccess.access_code).where(EscalationAccess.escalation_id == esc.escalation_id))
    access = acc_res.scalars().all()
    
    return {
        "escalationId": esc.escalation_id,
        "customerId": esc.customer_id,
        "title": esc.title,
        "severity": esc.severity,
        "slaDeadline": esc.sla_deadline,
        "status": esc.status,
        "requiredSkills": list(skills),
        "requiredAccess": list(access),
        "requiredDurationMinutes": esc.required_duration_minutes,
        "workaroundStatus": esc.workaround_status,
        "currentSpecialistId": esc.current_specialist_id,
        "sourceUpdatedAt": esc.updated_at
    }

@app.post("/escalations/{escalation_id}/assign", dependencies=[Depends(verify_tool_token)])
async def assign_specialist(escalation_id: str, payload: dict, db: AsyncSession = Depends(get_db)):
    await apply_failure_mode(db)
    
    specialist_id = payload.get("specialistId")
    idempotency_key = payload.get("idempotencyKey")
    
    # 1. Idempotency Check
    if idempotency_key:
        stmt = select(AssignmentHistory).where(AssignmentHistory.idempotency_key == idempotency_key)
        res = await db.execute(stmt)
        hist = res.scalar_one_or_none()
        if hist:
            # Re-fetch escalation
            stmt_esc = select(Escalation).where(Escalation.escalation_id == escalation_id)
            res_esc = await db.execute(stmt_esc)
            esc = res_esc.scalar_one()
            
            return {
                "escalationId": escalation_id,
                "previousSpecialistId": None,
                "currentSpecialistId": esc.current_specialist_id,
                "status": esc.status,
                "assignmentReference": f"ASN-{hist.history_id.split('-')[-1]}",
                "idempotencyKey": idempotency_key,
                "sourceUpdatedAt": esc.updated_at,
                "duplicate": True
            }
            
    # Fetch escalation
    stmt_esc = select(Escalation).where(Escalation.escalation_id == escalation_id)
    res_esc = await db.execute(stmt_esc)
    esc = res_esc.scalar_one_or_none()
    if not esc:
        raise HTTPException(status_code=404, detail=f"Escalation {escalation_id} not found")
        
    prev_specialist_id = esc.current_specialist_id
    esc.current_specialist_id = specialist_id
    esc.status = "ASSIGNED"
    esc.updated_at = datetime.now(timezone.utc).isoformat()
    db.add(esc)
    
    # Create History
    history_id = f"HIST-{random.randint(100, 999)}"
    history_record = AssignmentHistory(
        history_id=history_id,
        escalation_id=escalation_id,
        specialist_id=specialist_id,
        action="ASSIGNED",
        reason=payload.get("reason", "Autonomous reallocation"),
        occurred_at=datetime.now(timezone.utc).isoformat(),
        idempotency_key=idempotency_key
    )
    db.add(history_record)
    await db.commit()
    
    return {
        "escalationId": escalation_id,
        "previousSpecialistId": prev_specialist_id,
        "currentSpecialistId": specialist_id,
        "status": "ASSIGNED",
        "assignmentReference": f"ASN-{random.randint(500, 599)}",
        "idempotencyKey": idempotency_key,
        "sourceUpdatedAt": esc.updated_at
    }

@app.post("/escalations/{escalation_id}/status", dependencies=[Depends(verify_tool_token)])
async def update_status(escalation_id: str, payload: dict, db: AsyncSession = Depends(get_db)):
    await apply_failure_mode(db)
    stmt = select(Escalation).where(Escalation.escalation_id == escalation_id)
    res = await db.execute(stmt)
    esc = res.scalar_one_or_none()
    if not esc:
        raise HTTPException(status_code=404, detail=f"Escalation {escalation_id} not found")
        
    esc.status = payload.get("status", "OPEN")
    esc.updated_at = datetime.now(timezone.utc).isoformat()
    db.add(esc)
    await db.commit()
    return {"status": "success", "escalation_id": escalation_id, "status_value": esc.status}

# Admin endpoints
@app.post("/admin/escalations", dependencies=[Depends(verify_tool_token)])
async def create_admin_escalation(payload: dict, db: AsyncSession = Depends(get_db)):
    esc = Escalation(
        escalation_id=payload["escalationId"],
        customer_id=payload["customerId"],
        title=payload["title"],
        description=payload.get("description"),
        severity=payload["severity"],
        priority=payload["priority"],
        sla_deadline=payload.get("slaDeadline"),
        status=payload.get("status", "OPEN"),
        required_duration_minutes=payload.get("requiredDurationMinutes", 90),
        workaround_status=payload.get("workaroundStatus", "NONE"),
        current_specialist_id=payload.get("currentSpecialistId"),
        created_at=datetime.now(timezone.utc).isoformat(),
        updated_at=datetime.now(timezone.utc).isoformat(),
        scenario_id=settings.scenario_id
    )
    db.add(esc)
    
    # Skills
    for sk in payload.get("requiredSkills", []):
        db.add(EscalationSkill(escalation_id=esc.escalation_id, skill_code=sk))
        
    # Access
    for acc in payload.get("requiredAccess", []):
        db.add(EscalationAccess(escalation_id=esc.escalation_id, access_code=acc))
        
    await db.commit()
    return {"status": "success", "escalation_id": esc.escalation_id}

@app.post("/admin/escalations/{escalation_id}/sla-change", dependencies=[Depends(verify_tool_token)])
async def admin_sla_change(escalation_id: str, payload: dict, db: AsyncSession = Depends(get_db)):
    stmt = select(Escalation).where(Escalation.escalation_id == escalation_id)
    res = await db.execute(stmt)
    esc = res.scalar_one_or_none()
    if not esc:
        raise HTTPException(status_code=404, detail=f"Escalation {escalation_id} not found")
        
    esc.sla_deadline = payload.get("slaDeadline")
    esc.updated_at = datetime.now(timezone.utc).isoformat()
    db.add(esc)
    await db.commit()
    return {"status": "success", "escalation_id": escalation_id}

@app.post("/admin/escalations/{escalation_id}/workaround", dependencies=[Depends(verify_tool_token)])
async def admin_workaround(escalation_id: str, payload: dict, db: AsyncSession = Depends(get_db)):
    stmt = select(Escalation).where(Escalation.escalation_id == escalation_id)
    res = await db.execute(stmt)
    esc = res.scalar_one_or_none()
    if not esc:
        raise HTTPException(status_code=404, detail=f"Escalation {escalation_id} not found")
        
    esc.workaround_status = payload.get("workaroundStatus", "NONE")
    esc.updated_at = datetime.now(timezone.utc).isoformat()
    db.add(esc)
    await db.commit()
    return {"status": "success", "escalation_id": escalation_id}

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
