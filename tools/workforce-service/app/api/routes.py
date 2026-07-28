from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, Query, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database.models import FailureMode, Specialist
from app.database.session import get_db
from app.middleware.authentication import verify_tool_token
from app.schemas.requests import (
    AdminAvailabilityRequest,
    AdminCapacityRequest,
    AdminWorkloadRequest,
    LegacyTentativeReservationRequest,
    ReservationCreateRequest,
)
from app.schemas.responses import (
    ReservationResponse,
    ResetResponseData,
    SpecialistListData,
    SpecialistResponse,
    success_response,
)
from app.services.reservation_service import (
    cancel_reservation,
    confirm_reservation,
    create_legacy_tentative_reservation as create_legacy_tentative_reservation_record,
    create_reservation,
    get_reservation,
    reset_workforce,
)
from app.services.specialist_service import (
    WorkforceError,
    get_specialist,
    list_specialists,
    specialist_view_to_dict,
    specialist_view_to_legacy_dict,
)


router = APIRouter(
    prefix="/workforce/api/v1",
    tags=["workforce"],
    dependencies=[Depends(verify_tool_token)],
)
admin_router = APIRouter(tags=["admin"])
legacy_router = APIRouter(
    tags=["legacy-workforce"],
    dependencies=[Depends(verify_tool_token)],
)


def _specialist_response(view) -> SpecialistResponse:
    return SpecialistResponse(**specialist_view_to_dict(view))


def _reservation_data(reservation) -> dict:
    return ReservationResponse.model_validate(reservation).model_dump(mode="json")


@router.get("/specialists")
async def get_specialists(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    active: bool | None = Query(default=None),
    availability: bool | None = Query(default=None),
    skill: str | None = Query(default=None),
    min_available_capacity: int | None = Query(default=None, ge=0),
    search: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    result = await list_specialists(
        db,
        page=page,
        page_size=page_size,
        active=active,
        availability=availability,
        skill=skill,
        min_available_capacity=min_available_capacity,
        search=search,
    )
    data = SpecialistListData(
        specialists=[_specialist_response(view) for view in result.specialists],
        page=result.page,
        page_size=result.page_size,
        total_items=result.total_items,
        total_pages=result.total_pages,
    )
    return success_response(data.model_dump(mode="json"))


@router.get("/specialists/available")
async def get_available_specialists(
    skill: str | None = Query(default=None),
    required_capacity: int = Query(default=1, ge=1),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    result = await list_specialists(
        db,
        page=page,
        page_size=page_size,
        skill=skill,
        only_operationally_available=True,
        required_capacity=required_capacity,
    )
    data = SpecialistListData(
        specialists=[_specialist_response(view) for view in result.specialists],
        page=result.page,
        page_size=result.page_size,
        total_items=result.total_items,
        total_pages=result.total_pages,
    )
    return success_response(data.model_dump(mode="json"))


@router.get("/specialists/{specialist_id}")
async def get_specialist_by_id(specialist_id: str, db: AsyncSession = Depends(get_db)):
    view = await get_specialist(db, specialist_id)
    return success_response(_specialist_response(view).model_dump(mode="json"))


@router.post("/reservations", status_code=201)
async def create_reservation_record(
    payload: ReservationCreateRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    reservation, created = await create_reservation(db, payload)
    if not created:
        response.status_code = 200
        return success_response(_reservation_data(reservation), message="Reservation already exists")
    return success_response(_reservation_data(reservation), message="Reservation created successfully")


@router.get("/reservations/{reservation_id}")
async def get_reservation_by_id(reservation_id: str, db: AsyncSession = Depends(get_db)):
    reservation = await get_reservation(db, reservation_id)
    return success_response(_reservation_data(reservation))


@router.patch("/reservations/{reservation_id}/confirm")
async def confirm_reservation_record(reservation_id: str, db: AsyncSession = Depends(get_db)):
    reservation = await confirm_reservation(db, reservation_id)
    return success_response(_reservation_data(reservation), message="Reservation confirmed successfully")


@router.delete("/reservations/{reservation_id}")
async def cancel_reservation_record(
    reservation_id: str,
    cancellation_reason: str | None = Query(default=None, max_length=1000),
    db: AsyncSession = Depends(get_db),
):
    reason = cancellation_reason.strip() if cancellation_reason else None
    reservation = await cancel_reservation(db, reservation_id, cancellation_reason=reason)
    return success_response(_reservation_data(reservation), message="Reservation cancelled successfully")


def verify_admin_key(x_admin_key: str | None = Header(default=None, alias="X-Admin-Key")) -> None:
    settings = get_settings()
    if not settings.admin_api_key:
        raise WorkforceError(503, "WORKFORCE_503", "Admin reset is not configured")
    if x_admin_key != settings.admin_api_key:
        raise WorkforceError(401, "WORKFORCE_401", "Invalid admin credentials")


@admin_router.post("/admin/reset", dependencies=[Depends(verify_admin_key)])
async def reset_workforce_database(db: AsyncSession = Depends(get_db)):
    counts = await reset_workforce(db)
    data = ResetResponseData(**counts)
    return success_response(data.model_dump(mode="json"), message="Workforce database reset successfully")


@legacy_router.get("/specialists", deprecated=True)
async def get_legacy_specialists(db: AsyncSession = Depends(get_db)):
    result = await list_specialists(db, page=1, page_size=100)
    return [specialist_view_to_legacy_dict(view) for view in result.specialists]


@legacy_router.get("/specialists/{specialist_id}", deprecated=True)
async def get_legacy_specialist_by_id(specialist_id: str, db: AsyncSession = Depends(get_db)):
    view = await get_specialist(db, specialist_id)
    return specialist_view_to_legacy_dict(view)


@legacy_router.get("/availability", deprecated=True)
async def get_legacy_availability(db: AsyncSession = Depends(get_db)):
    result = await list_specialists(db, page=1, page_size=100, only_operationally_available=True)
    return {
        "specialists": [
            {
                "specialistId": view.specialist.specialist_id,
                "availableCapacity": view.available_capacity,
                "currentAssignmentCount": view.specialist.current_workload,
                "maximumConcurrentAssignments": view.specialist.capacity,
                "operationalFatigueLevel": "LOW",
            }
            for view in result.specialists
        ],
        "sourceUpdatedAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }


@legacy_router.get("/workload", deprecated=True)
async def get_legacy_workload(db: AsyncSession = Depends(get_db)):
    result = await list_specialists(db, page=1, page_size=100)
    return [
        {
            "specialistId": view.specialist.specialist_id,
            "activeAssignmentCount": view.specialist.current_workload,
            "effectiveWorkload": view.effective_workload,
            "availableCapacity": view.available_capacity,
            "updatedAt": view.specialist.updated_at,
        }
        for view in result.specialists
    ]


@legacy_router.post("/reservations/tentative", deprecated=True)
async def create_legacy_tentative_reservation(
    payload: LegacyTentativeReservationRequest,
    db: AsyncSession = Depends(get_db),
):
    reservation = await create_legacy_tentative_reservation_record(
        db,
        specialist_id=payload.specialistId,
        incident_id=payload.escalationId,
        reservation_id=payload.idempotencyKey,
        run_id=payload.runId,
    )
    return {
        "reservationId": reservation.reservation_id,
        "status": reservation.status,
        "specialistId": reservation.specialist_id,
        "escalationId": reservation.incident_id,
        "expiresAt": reservation.expires_at,
    }


@legacy_router.post("/reservations/{reservation_id}/confirm", deprecated=True)
async def confirm_legacy_reservation(reservation_id: str, db: AsyncSession = Depends(get_db)):
    reservation = await confirm_reservation(db, reservation_id)
    return {
        "reservationId": reservation.reservation_id,
        "status": reservation.status,
        "specialistId": reservation.specialist_id,
        "escalationId": reservation.incident_id,
    }


@legacy_router.delete("/reservations/{reservation_id}", deprecated=True)
async def delete_legacy_reservation(reservation_id: str, db: AsyncSession = Depends(get_db)):
    reservation = await cancel_reservation(db, reservation_id)
    return {"status": "success", "reservation_id": reservation.reservation_id, "message": "Reservation cancelled"}


@legacy_router.post("/admin/specialists/{specialist_id}/unavailable", deprecated=True)
async def admin_set_unavailable(
    specialist_id: str,
    payload: AdminAvailabilityRequest,
    db: AsyncSession = Depends(get_db),
):
    view = await get_specialist(db, specialist_id)
    specialist = view.specialist
    specialist.availability = not payload.unavailable
    specialist.updated_at = datetime.now(timezone.utc)
    db.add(specialist)
    await db.commit()
    return {"status": "success", "specialist_id": specialist.specialist_id, "availability": specialist.availability}


@legacy_router.post("/admin/specialists/{specialist_id}/capacity", deprecated=True)
async def admin_set_capacity(specialist_id: str, payload: AdminCapacityRequest, db: AsyncSession = Depends(get_db)):
    view = await get_specialist(db, specialist_id)
    specialist = view.specialist
    if payload.maximumConcurrentAssignments < specialist.current_workload:
        raise WorkforceError(409, "WORKFORCE_409", "Capacity cannot be below current workload")
    specialist.capacity = payload.maximumConcurrentAssignments
    specialist.updated_at = datetime.now(timezone.utc)
    db.add(specialist)
    await db.commit()
    return {"status": "success", "specialist_id": specialist.specialist_id}


@legacy_router.post("/admin/workload/{specialist_id}", deprecated=True)
async def admin_set_workload(specialist_id: str, payload: AdminWorkloadRequest, db: AsyncSession = Depends(get_db)):
    view = await get_specialist(db, specialist_id)
    specialist = view.specialist
    if payload.current_workload is None:
        return {"status": "success", "specialist_id": specialist.specialist_id}
    if payload.current_workload > specialist.capacity:
        raise WorkforceError(409, "WORKFORCE_409", "Workload cannot exceed capacity")
    specialist.current_workload = payload.current_workload
    specialist.updated_at = datetime.now(timezone.utc)
    db.add(specialist)
    await db.commit()
    return {
        "status": "success",
        "specialist_id": specialist.specialist_id,
        "activeAssignmentCount": specialist.current_workload,
    }


@legacy_router.post("/admin/failure-mode", deprecated=True)
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
