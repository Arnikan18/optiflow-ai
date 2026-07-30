from datetime import datetime

from fastapi import APIRouter, Depends, Header, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database.session import get_db
from app.middleware.authentication import verify_tool_token
from app.schemas.requests import (
    IncidentAssignmentRequest,
    IncidentAssignmentVerificationRequest,
    IncidentCreateRequest,
    IncidentSimulationFieldUpdateRequest,
    IncidentSimulationLoadStateRequest,
    IncidentSimulationResolveRequest,
    IncidentStatusUpdateRequest,
)
from app.schemas.responses import (
    IncidentAssignmentVerificationResponse,
    IncidentListData,
    IncidentResponse,
    ResetResponseData,
    success_response,
)
from app.services.incident_service import (
    IncidentError,
    assign_specialist,
    create_incident,
    get_incident,
    get_legacy_escalation,
    load_simulation_incidents,
    list_incidents,
    list_legacy_escalations,
    resolve_incident_for_simulation,
    reset_incidents,
    update_incident_status,
    update_incident_simulation_fields,
    verify_incident_assignment,
)


router = APIRouter(
    prefix="/incident/api/v1",
    tags=["incidents"],
    dependencies=[Depends(verify_tool_token)],
)
admin_router = APIRouter(tags=["admin"])
legacy_router = APIRouter(
    tags=["legacy-escalations"],
    dependencies=[Depends(verify_tool_token)],
)


def _incident_data(incident) -> dict:
    return IncidentResponse.model_validate(incident).model_dump(mode="json")


@router.post("/incidents", status_code=status.HTTP_201_CREATED)
async def create_incident_record(payload: IncidentCreateRequest, db: AsyncSession = Depends(get_db)):
    incident = await create_incident(db, payload)
    return success_response(_incident_data(incident), message="Incident created successfully")


@router.get("/incidents")
async def get_incidents(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status: str | None = Query(default=None),
    priority: str | None = Query(default=None),
    customer_id: str | None = Query(default=None),
    assigned_specialist_id: str | None = Query(default=None),
    unassigned: bool | None = Query(default=None),
    overdue: bool | None = Query(default=None),
    search: str | None = Query(default=None),
    sla_before: datetime | None = Query(default=None),
    sla_after: datetime | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    result = await list_incidents(
        db,
        page=page,
        page_size=page_size,
        status=status,
        priority=priority,
        customer_id=customer_id,
        assigned_specialist_id=assigned_specialist_id,
        unassigned=unassigned,
        overdue=overdue,
        search=search,
        sla_before=sla_before,
        sla_after=sla_after,
    )
    data = IncidentListData(
        incidents=[IncidentResponse.model_validate(incident) for incident in result.incidents],
        page=result.page,
        page_size=result.page_size,
        total_items=result.total_items,
        total_pages=result.total_pages,
    )
    return success_response(data.model_dump(mode="json"))


@router.get("/incidents/{incident_id}")
async def get_incident_by_id(incident_id: str, db: AsyncSession = Depends(get_db)):
    incident = await get_incident(db, incident_id)
    return success_response(_incident_data(incident))


@router.patch("/incidents/{incident_id}/status")
async def update_incident_status_record(
    incident_id: str,
    payload: IncidentStatusUpdateRequest,
    db: AsyncSession = Depends(get_db),
):
    incident = await update_incident_status(db, incident_id, payload)
    return success_response(_incident_data(incident), message="Incident status updated successfully")


@router.post("/incidents/{incident_id}/assign")
async def assign_incident_specialist(
    incident_id: str,
    payload: IncidentAssignmentRequest,
    db: AsyncSession = Depends(get_db),
):
    incident = await assign_specialist(db, incident_id, payload)
    return success_response(_incident_data(incident), message="Incident assignment updated successfully")


@router.post("/incidents/assignment/verify")
async def verify_incident_assignment_record(
    payload: IncidentAssignmentVerificationRequest,
    db: AsyncSession = Depends(get_db),
):
    data = await verify_incident_assignment(db, payload)
    return success_response(IncidentAssignmentVerificationResponse(**data).model_dump(mode="json"))


@router.patch("/incidents/{incident_id}/simulation-fields")
async def update_incident_simulation_fields_record(
    incident_id: str,
    payload: IncidentSimulationFieldUpdateRequest,
    db: AsyncSession = Depends(get_db),
):
    incident = await update_incident_simulation_fields(db, incident_id, payload)
    return success_response(_incident_data(incident), message="Incident simulation fields updated successfully")


@router.post("/incidents/{incident_id}/simulation-resolve")
async def resolve_incident_simulation_record(
    incident_id: str,
    payload: IncidentSimulationResolveRequest,
    db: AsyncSession = Depends(get_db),
):
    incident = await resolve_incident_for_simulation(db, incident_id, payload)
    return success_response(_incident_data(incident), message="Incident resolved by simulation")


def verify_admin_key(x_admin_key: str | None = Header(default=None, alias="X-Admin-Key")) -> None:
    settings = get_settings()
    if not settings.admin_api_key:
        raise IncidentError(503, "INCIDENT_503", "Admin reset is not configured")
    if x_admin_key != settings.admin_api_key:
        raise IncidentError(401, "INCIDENT_401", "Invalid admin credentials")


@admin_router.post("/admin/reset", dependencies=[Depends(verify_admin_key)])
async def reset_incident_database(db: AsyncSession = Depends(get_db)):
    seeded_records = await reset_incidents(db)
    data = ResetResponseData(seeded_records=seeded_records)
    return success_response(data.model_dump(mode="json"), message="Incident database reset successfully")


@admin_router.post("/admin/simulation/load-state", dependencies=[Depends(verify_admin_key)])
async def load_incident_simulation_state(
    payload: IncidentSimulationLoadStateRequest,
    db: AsyncSession = Depends(get_db),
):
    data = await load_simulation_incidents(db, payload)
    return success_response(data, message="Incident simulation state loaded")


@legacy_router.get("/escalations", deprecated=True)
async def get_legacy_escalations(db: AsyncSession = Depends(get_db)):
    return await list_legacy_escalations(db)


@legacy_router.get("/escalations/active", deprecated=True)
async def get_legacy_active_escalations(db: AsyncSession = Depends(get_db)):
    return await list_legacy_escalations(db, active_only=True)


@legacy_router.get("/escalations/{escalation_id}", deprecated=True)
async def get_legacy_escalation_by_id(escalation_id: str, db: AsyncSession = Depends(get_db)):
    return await get_legacy_escalation(db, escalation_id)
