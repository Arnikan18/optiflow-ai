import os
import contextlib
import random
import asyncio
from fastapi import FastAPI, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timezone, timedelta

from app.config import settings
from app.database.session import get_db, engine
from app.database.base import Base
from app.database.models import AssignmentRequest, Notification, ConfiguredResponse, FailureMode
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
    title="OptiFlow Communication Service Mock",
    version="4.0",
    lifespan=lifespan
)

app.add_middleware(RequestContextMiddleware)

@app.get("/health")
async def health(db: AsyncSession = Depends(get_db)):
    try:
        await db.execute(select(AssignmentRequest).limit(1))
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

# Helper to execute configured specialist response in background
async def process_delayed_response(request_id: str, delay_ms: int, next_status: str, reason: str):
    await asyncio.sleep(delay_ms / 1000.0)
    async with AsyncSession(engine) as session:
        stmt = select(AssignmentRequest).where(AssignmentRequest.request_id == request_id)
        res = await session.execute(stmt)
        req = res.scalar_one_or_none()
        if req and req.status == "PENDING":
            req.status = next_status
            req.response_reason = reason
            req.responded_at = datetime.now(timezone.utc).isoformat()
            session.add(req)
            await session.commit()

@app.post("/assignment-requests", dependencies=[Depends(verify_tool_token)])
async def create_assignment_request(payload: dict, db: AsyncSession = Depends(get_db)):
    await apply_failure_mode(db)
    
    specialist_id = payload.get("specialistId")
    escalation_id = payload.get("escalationId")
    requested_minutes = payload.get("requestedMinutes", 90)
    idempotency_key = payload.get("idempotencyKey")
    
    # 1. Idempotency Check
    if idempotency_key:
        stmt = select(AssignmentRequest).where(AssignmentRequest.idempotency_key == idempotency_key)
        res = await db.execute(stmt)
        req = res.scalar_one_or_none()
        if req:
            return {
                "requestId": req.request_id,
                "status": req.status,
                "specialistId": req.specialist_id,
                "escalationId": req.escalation_id,
                "duplicate": True
            }
            
    request_id = f"REQ-{random.randint(100, 999)}"
    
    # Check configured responses
    stmt_cfg = select(ConfiguredResponse).where(
        ConfiguredResponse.specialist_id == specialist_id,
        ConfiguredResponse.active == 1
    ).limit(1)
    res_cfg = await db.execute(stmt_cfg)
    cfg = res_cfg.scalar_one_or_none()
    
    initial_status = "PENDING"
    
    req = AssignmentRequest(
        request_id=request_id,
        specialist_id=specialist_id,
        escalation_id=escalation_id,
        requested_minutes=requested_minutes,
        status=initial_status,
        idempotency_key=idempotency_key,
        created_at=datetime.now(timezone.utc).isoformat(),
        scenario_id=settings.scenario_id
    )
    db.add(req)
    await db.commit()
    
    # Trigger background response if configured
    if cfg:
        asyncio.create_task(
            process_delayed_response(
                request_id=request_id,
                delay_ms=cfg.delay_ms,
                next_status=cfg.next_status,
                reason=cfg.response_reason or ""
            )
        )
    else:
        # Default auto-accept after 1 second for other specialists
        asyncio.create_task(
            process_delayed_response(
                request_id=request_id,
                delay_ms=1000,
                next_status="ACCEPTED",
                reason="Auto-accepted"
            )
        )
        
    return {
        "requestId": request_id,
        "status": "PENDING",
        "specialistId": specialist_id,
        "escalationId": escalation_id
    }

@app.get("/assignment-requests/{request_id}", dependencies=[Depends(verify_tool_token)])
async def get_assignment_request(request_id: str, db: AsyncSession = Depends(get_db)):
    await apply_failure_mode(db)
    stmt = select(AssignmentRequest).where(AssignmentRequest.request_id == request_id)
    res = await db.execute(stmt)
    req = res.scalar_one_or_none()
    if not req:
        raise HTTPException(status_code=404, detail=f"Request {request_id} not found")
        
    return {
        "requestId": req.request_id,
        "status": req.status,
        "specialistId": req.specialist_id,
        "escalationId": req.escalation_id,
        "responseReason": req.response_reason,
        "respondedAt": req.responded_at
    }

@app.post("/assignment-requests/{request_id}/respond", dependencies=[Depends(verify_tool_token)])
async def respond_to_request(request_id: str, payload: dict, db: AsyncSession = Depends(get_db)):
    await apply_failure_mode(db)
    stmt = select(AssignmentRequest).where(AssignmentRequest.request_id == request_id)
    res = await db.execute(stmt)
    req = res.scalar_one_or_none()
    if not req:
        raise HTTPException(status_code=404, detail=f"Request {request_id} not found")
        
    req.status = payload.get("status", "ACCEPTED")
    req.response_reason = payload.get("reason")
    req.responded_at = datetime.now(timezone.utc).isoformat()
    db.add(req)
    await db.commit()
    return {"status": "success", "requestId": request_id, "status_value": req.status}

@app.post("/notifications", dependencies=[Depends(verify_tool_token)])
async def create_notification(payload: dict, db: AsyncSession = Depends(get_db)):
    await apply_failure_mode(db)
    
    notification_id = f"NTF-{random.randint(100, 999)}"
    idempotency_key = payload.get("idempotencyKey")
    
    if idempotency_key:
        stmt = select(Notification).where(Notification.idempotency_key == idempotency_key)
        res = await db.execute(stmt)
        ntf = res.scalar_one_or_none()
        if ntf:
            return {
                "notificationId": ntf.notification_id,
                "status": ntf.delivery_status,
                "duplicate": True
            }
            
    ntf = Notification(
        notification_id=notification_id,
        recipient_type=payload["recipientType"],
        recipient_id=payload["recipientId"],
        notification_type=payload["notificationType"],
        message=payload["message"],
        delivery_status="DELIVERED",
        idempotency_key=idempotency_key,
        created_at=datetime.now(timezone.utc).isoformat(),
        delivered_at=datetime.now(timezone.utc).isoformat()
    )
    db.add(ntf)
    await db.commit()
    
    return {
        "notificationId": notification_id,
        "status": "DELIVERED"
    }

@app.get("/notifications/{notification_id}", dependencies=[Depends(verify_tool_token)])
async def get_notification(notification_id: str, db: AsyncSession = Depends(get_db)):
    await apply_failure_mode(db)
    stmt = select(Notification).where(Notification.notification_id == notification_id)
    res = await db.execute(stmt)
    ntf = res.scalar_one_or_none()
    if not ntf:
        raise HTTPException(status_code=404, detail=f"Notification {notification_id} not found")
        
    return {
        "notificationId": ntf.notification_id,
        "recipientType": ntf.recipient_type,
        "recipientId": ntf.recipient_id,
        "message": ntf.message,
        "deliveryStatus": ntf.delivery_status,
        "deliveredAt": ntf.delivered_at
    }

# Admin tools
@app.post("/admin/next-response", dependencies=[Depends(verify_tool_token)])
async def configure_next_response(payload: dict, db: AsyncSession = Depends(get_db)):
    stmt = select(ConfiguredResponse).where(ConfiguredResponse.specialist_id == payload.get("specialistId"))
    res = await db.execute(stmt)
    cfg = res.scalar_one_or_none()
    if not cfg:
        cfg = ConfiguredResponse(specialist_id=payload.get("specialistId"), next_status="ACCEPTED", delay_ms=0, active=1, updated_at="")
        
    cfg.next_status = payload.get("status", "ACCEPTED")
    cfg.response_reason = payload.get("reason")
    cfg.delay_ms = payload.get("delayMs", 1000)
    cfg.active = 1
    cfg.updated_at = datetime.now(timezone.utc).isoformat()
    
    db.add(cfg)
    await db.commit()
    return {"status": "success"}

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
