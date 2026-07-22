import os
import contextlib
import random
from fastapi import FastAPI, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timezone, timedelta

from app.config import settings
from app.database.session import get_db, engine
from app.database.base import Base
from app.database.models import Specialist, SpecialistSkill, SpecialistAccess, AvailabilitySlot, WorkloadRecord, Reservation, FailureMode
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
    title="OptiFlow Workforce Service Mock",
    version="4.0",
    lifespan=lifespan
)

app.add_middleware(RequestContextMiddleware)

@app.get("/health")
async def health(db: AsyncSession = Depends(get_db)):
    try:
        await db.execute(select(Specialist).limit(1))
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

@app.get("/specialists", dependencies=[Depends(verify_tool_token)])
async def get_specialists(db: AsyncSession = Depends(get_db)):
    await apply_failure_mode(db)
    result = await db.execute(select(Specialist))
    specs = result.scalars().all()
    
    response_data = []
    for sp in specs:
        sk_res = await db.execute(select(SpecialistSkill.skill_code).where(SpecialistSkill.specialist_id == sp.specialist_id))
        skills = sk_res.scalars().all()
        
        acc_res = await db.execute(select(SpecialistAccess.access_code).where(SpecialistAccess.specialist_id == sp.specialist_id))
        access = acc_res.scalars().all()
        
        response_data.append({
            "specialistId": sp.specialist_id,
            "name": sp.name,
            "skills": list(skills),
            "accessPermissions": list(access),
            "maximumConcurrentAssignments": sp.max_concurrent_assignments,
            "protectedEmergencyMinutes": sp.protected_emergency_minutes,
            "created_at": sp.created_at,
            "updated_at": sp.updated_at
        })
    return response_data

@app.get("/specialists/{specialist_id}", dependencies=[Depends(verify_tool_token)])
async def get_specialist(specialist_id: str, db: AsyncSession = Depends(get_db)):
    await apply_failure_mode(db)
    stmt = select(Specialist).where(Specialist.specialist_id == specialist_id)
    res = await db.execute(stmt)
    sp = res.scalar_one_or_none()
    if not sp:
        raise HTTPException(status_code=404, detail=f"Specialist {specialist_id} not found")
        
    sk_res = await db.execute(select(SpecialistSkill.skill_code).where(SpecialistSkill.specialist_id == sp.specialist_id))
    skills = sk_res.scalars().all()
    
    acc_res = await db.execute(select(SpecialistAccess.access_code).where(SpecialistAccess.specialist_id == sp.specialist_id))
    access = acc_res.scalars().all()
    
    return {
        "specialistId": sp.specialist_id,
        "name": sp.name,
        "skills": list(skills),
        "accessPermissions": list(access),
        "maximumConcurrentAssignments": sp.max_concurrent_assignments,
        "protectedEmergencyMinutes": sp.protected_emergency_minutes,
        "created_at": sp.created_at,
        "updated_at": sp.updated_at
    }

@app.get("/availability", dependencies=[Depends(verify_tool_token)])
async def get_availability(
    from_time: str = Query(alias="from"),
    to_time: str = Query(alias="to"),
    db: AsyncSession = Depends(get_db)
):
    await apply_failure_mode(db)
    
    # Query specialists and availability slots
    res_specs = await db.execute(select(Specialist).where(Specialist.active == 1))
    specs = res_specs.scalars().all()
    
    response_list = []
    
    # Filter availability
    for sp in specs:
        # Get availability slots
        res_slots = await db.execute(select(AvailabilitySlot).where(AvailabilitySlot.specialist_id == sp.specialist_id))
        slots = res_slots.scalars().all()
        
        # Get workload
        res_wl = await db.execute(select(WorkloadRecord).where(WorkloadRecord.specialist_id == sp.specialist_id))
        wl = res_wl.scalar_one_or_none()
        
        # Get active reservations (not expired, or confirmed)
        res_rsv = await db.execute(select(Reservation).where(Reservation.specialist_id == sp.specialist_id))
        reservations = res_rsv.scalars().all()
        
        for slot in slots:
            # Check overlap between slot [slot.available_from, slot.available_until] and requested window [from_time, to_time]
            try:
                s_from = datetime.fromisoformat(slot.available_from.replace("Z", "+00:00"))
                s_until = datetime.fromisoformat(slot.available_until.replace("Z", "+00:00"))
                req_from = datetime.fromisoformat(from_time.replace("Z", "+00:00"))
                req_to = datetime.fromisoformat(to_time.replace("Z", "+00:00"))
                
                overlap_start = max(s_from, req_from)
                overlap_end = min(s_until, req_to)
                
                if overlap_start < overlap_end:
                    available_minutes = int((overlap_end - overlap_start).total_seconds() / 60)
                    
                    # Deduct minutes of existing reservations in this window
                    for rsv in reservations:
                        if rsv.status in ("TENTATIVE", "CONFIRMED"):
                            r_start = datetime.fromisoformat(rsv.start_at.replace("Z", "+00:00"))
                            r_end = datetime.fromisoformat(rsv.end_at.replace("Z", "+00:00"))
                            r_overlap_start = max(overlap_start, r_start)
                            r_overlap_end = min(overlap_end, r_end)
                            if r_overlap_start < r_overlap_end:
                                r_minutes = int((r_overlap_end - r_overlap_start).total_seconds() / 60)
                                available_minutes -= r_minutes
                                
                    available_minutes = max(0, available_minutes)
                    
                    response_list.append({
                        "specialistId": sp.specialist_id,
                        "availableFrom": overlap_start.isoformat().replace("+00:00", "Z"),
                        "availableUntil": overlap_end.isoformat().replace("+00:00", "Z"),
                        "availableMinutes": available_minutes,
                        "currentAssignmentCount": wl.active_assignment_count if wl else 0,
                        "maximumConcurrentAssignments": sp.max_concurrent_assignments,
                        "operationalFatigueLevel": "LOW" if (wl.overnight_incident_count if wl else 0) < 2 else "HIGH"
                    })
            except ValueError:
                pass
                
    return {
        "specialists": response_list,
        "sourceUpdatedAt": datetime.now(timezone.utc).isoformat()
    }

@app.get("/workload", dependencies=[Depends(verify_tool_token)])
async def get_workload(db: AsyncSession = Depends(get_db)):
    await apply_failure_mode(db)
    result = await db.execute(select(WorkloadRecord))
    wl_records = result.scalars().all()
    
    response_data = []
    for wl in wl_records:
        response_data.append({
            "specialistId": wl.specialist_id,
            "activeAssignmentCount": wl.active_assignment_count,
            "assignedMinutes": wl.assigned_minutes,
            "afterHoursMinutes": wl.after_hours_minutes,
            "overnightIncidentCount": wl.overnight_incident_count,
            "recentInterruptionCount": wl.recent_interruption_count,
            "updatedAt": wl.updated_at
        })
    return response_data

@app.post("/reservations/tentative", dependencies=[Depends(verify_tool_token)])
async def create_tentative_reservation(payload: dict, db: AsyncSession = Depends(get_db)):
    await apply_failure_mode(db)
    
    specialist_id = payload.get("specialistId")
    escalation_id = payload.get("escalationId")
    start_at = payload.get("startAt")
    end_at = payload.get("endAt")
    idempotency_key = payload.get("idempotencyKey")
    
    # 1. Idempotency Check
    if idempotency_key:
        stmt = select(Reservation).where(Reservation.idempotency_key == idempotency_key)
        res = await db.execute(stmt)
        rsv = res.scalar_one_or_none()
        if rsv:
            return {
                "reservationId": rsv.reservation_id,
                "status": rsv.status,
                "specialistId": rsv.specialist_id,
                "escalationId": rsv.escalation_id,
                "expiresAt": (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat().replace("+00:00", "Z"),
                "duplicate": True
            }
            
    # Check specialist capacity / availability first
    stmt_spec = select(Specialist).where(Specialist.specialist_id == specialist_id)
    res_spec = await db.execute(stmt_spec)
    spec = res_spec.scalar_one_or_none()
    if not spec:
        raise HTTPException(status_code=404, detail=f"Specialist {specialist_id} not found")
        
    reservation_id = f"RSV-{random.randint(100, 999)}"
    expires_at = (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat().replace("+00:00", "Z")
    
    rsv = Reservation(
        reservation_id=reservation_id,
        specialist_id=specialist_id,
        escalation_id=escalation_id,
        start_at=start_at,
        end_at=end_at,
        status="TENTATIVE",
        idempotency_key=idempotency_key,
        created_at=datetime.now(timezone.utc).isoformat(),
        updated_at=datetime.now(timezone.utc).isoformat()
    )
    db.add(rsv)
    await db.commit()
    
    return {
        "reservationId": reservation_id,
        "status": "TENTATIVE",
        "specialistId": specialist_id,
        "escalationId": escalation_id,
        "expiresAt": expires_at
    }

@app.post("/reservations/{reservation_id}/confirm", dependencies=[Depends(verify_tool_token)])
async def confirm_reservation(reservation_id: str, db: AsyncSession = Depends(get_db)):
    await apply_failure_mode(db)
    stmt = select(Reservation).where(Reservation.reservation_id == reservation_id)
    res = await db.execute(stmt)
    rsv = res.scalar_one_or_none()
    if not rsv:
        raise HTTPException(status_code=404, detail=f"Reservation {reservation_id} not found")
        
    rsv.status = "CONFIRMED"
    rsv.updated_at = datetime.now(timezone.utc).isoformat()
    
    # Also update specialist workload
    res_wl = await db.execute(select(WorkloadRecord).where(WorkloadRecord.specialist_id == rsv.specialist_id))
    wl = res_wl.scalar_one_or_none()
    if wl:
        wl.active_assignment_count += 1
        # Compute duration
        try:
            s = datetime.fromisoformat(rsv.start_at.replace("Z", "+00:00"))
            e = datetime.fromisoformat(rsv.end_at.replace("Z", "+00:00"))
            wl.assigned_minutes += int((e - s).total_seconds() / 60)
        except ValueError:
            pass
        wl.updated_at = datetime.now(timezone.utc).isoformat()
        db.add(wl)
        
    db.add(rsv)
    await db.commit()
    
    return {
        "reservationId": reservation_id,
        "status": "CONFIRMED",
        "specialistId": rsv.specialist_id,
        "escalationId": rsv.escalation_id
    }

@app.delete("/reservations/{reservation_id}", dependencies=[Depends(verify_tool_token)])
async def delete_reservation(reservation_id: str, db: AsyncSession = Depends(get_db)):
    await apply_failure_mode(db)
    stmt = select(Reservation).where(Reservation.reservation_id == reservation_id)
    res = await db.execute(stmt)
    rsv = res.scalar_one_or_none()
    if not rsv:
        raise HTTPException(status_code=404, detail=f"Reservation {reservation_id} not found")
        
    rsv.status = "CANCELLED"
    rsv.updated_at = datetime.now(timezone.utc).isoformat()
    db.add(rsv)
    await db.commit()
    return {"status": "success", "reservation_id": reservation_id, "message": "Reservation cancelled"}

# Admin tools
@app.post("/admin/specialists/{specialist_id}/unavailable", dependencies=[Depends(verify_tool_token)])
async def admin_set_unavailable(specialist_id: str, payload: dict, db: AsyncSession = Depends(get_db)):
    # Delete availability slots or change active status
    stmt = select(Specialist).where(Specialist.specialist_id == specialist_id)
    res = await db.execute(stmt)
    spec = res.scalar_one_or_none()
    if not spec:
        raise HTTPException(status_code=404, detail=f"Specialist {specialist_id} not found")
        
    spec.active = 0 if payload.get("unavailable", False) else 1
    spec.updated_at = datetime.now(timezone.utc).isoformat()
    db.add(spec)
    await db.commit()
    return {"status": "success", "specialist_id": specialist_id, "active": spec.active}

@app.post("/admin/specialists/{specialist_id}/capacity", dependencies=[Depends(verify_tool_token)])
async def admin_set_capacity(specialist_id: str, payload: dict, db: AsyncSession = Depends(get_db)):
    stmt = select(Specialist).where(Specialist.specialist_id == specialist_id)
    res = await db.execute(stmt)
    spec = res.scalar_one_or_none()
    if not spec:
        raise HTTPException(status_code=404, detail=f"Specialist {specialist_id} not found")
        
    spec.max_concurrent_assignments = payload.get("maximumConcurrentAssignments", 1)
    spec.updated_at = datetime.now(timezone.utc).isoformat()
    db.add(spec)
    await db.commit()
    return {"status": "success", "specialist_id": specialist_id}

@app.post("/admin/workload/{specialist_id}", dependencies=[Depends(verify_tool_token)])
async def admin_set_workload(specialist_id: str, payload: dict, db: AsyncSession = Depends(get_db)):
    stmt = select(WorkloadRecord).where(WorkloadRecord.specialist_id == specialist_id)
    res = await db.execute(stmt)
    wl = res.scalar_one_or_none()
    if not wl:
        raise HTTPException(status_code=404, detail=f"Workload record for specialist {specialist_id} not found")
        
    wl.after_hours_minutes = payload.get("afterHoursMinutes", wl.after_hours_minutes)
    wl.overnight_incident_count = payload.get("overnightIncidentCount", wl.overnight_incident_count)
    wl.recent_interruption_count = payload.get("recentInterruptionCount", wl.recent_interruption_count)
    wl.updated_at = datetime.now(timezone.utc).isoformat()
    
    db.add(wl)
    await db.commit()
    return {"status": "success", "specialist_id": specialist_id}

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
