from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, Query, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import settings
from app.main_dependencies import get_db
from app.simulation.scenario_loader import get_scenario_loader
from app.simulation.schemas import (
    EventHistoryData,
    JudgeEventRequest,
    NotificationListData,
    ScenarioListData,
    SimulationError,
    StartSimulationRequest,
)
from app.simulation.timeline_simulator import get_timeline_simulator


router = APIRouter(prefix="/api/v1/simulation", tags=["simulation"])


class ResetSimulationRequest(BaseModel):
    scenario_id: str | None = None


def _jsonable(data: Any) -> Any:
    if isinstance(data, BaseModel):
        return data.model_dump(mode="json")
    if isinstance(data, list):
        return [_jsonable(item) for item in data]
    if isinstance(data, dict):
        return {key: _jsonable(value) for key, value in data.items()}
    return data


def success_response(data: Any, message: str = "Request completed successfully") -> dict[str, Any]:
    from app.demo.service import utc_timestamp

    return {
        "success": True,
        "message": message,
        "timestamp": utc_timestamp(),
        "data": _jsonable(data),
    }


def error_response(message: str, error_code: str, *, details: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    from app.demo.service import utc_timestamp

    response: dict[str, Any] = {
        "success": False,
        "message": message,
        "errorCode": error_code,
        "timestamp": utc_timestamp(),
    }
    if details:
        response["details"] = details
    return response


def request_id_header(x_request_id: str | None = Header(default=None, alias="X-Request-ID")) -> str:
    return x_request_id.strip() if x_request_id and x_request_id.strip() else str(uuid4())


def ensure_demo_mode() -> None:
    if not settings.demo_mode:
        raise SimulationError(403, "SIMULATION_DEMO_MODE_DISABLED", "Demo mode is disabled")


def ensure_admin_key(x_admin_key: str | None) -> None:
    if not settings.admin_api_key:
        raise SimulationError(503, "SIMULATION_ADMIN_NOT_CONFIGURED", "Admin controls are not configured")
    if x_admin_key != settings.admin_api_key:
        raise SimulationError(401, "SIMULATION_ADMIN_UNAUTHORIZED", "Invalid admin credentials")


def mutation_auth_error(x_admin_key: str | None, request_id: str) -> JSONResponse | None:
    try:
        ensure_demo_mode()
        ensure_admin_key(x_admin_key)
    except SimulationError as exc:
        return _simulation_error_response(exc, request_id)
    return None


def _simulation_error_response(exc: SimulationError, request_id: str) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        headers={"X-Request-ID": request_id},
        content=error_response(exc.message, exc.error_code, details=exc.details),
    )


async def _wrap(call, response: Response, request_id: str, message: str = "Request completed successfully"):
    response.headers["X-Request-ID"] = request_id
    try:
        return success_response(await call, message=message)
    except SimulationError as exc:
        return _simulation_error_response(exc, request_id)


@router.get("/scenarios")
async def list_scenarios(
    response: Response,
    reload: bool = Query(default=False),
    request_id: str = Depends(request_id_header),
):
    response.headers["X-Request-ID"] = request_id
    try:
        data: ScenarioListData = get_scenario_loader().list_scenarios(reload=reload)
        return success_response(data)
    except SimulationError as exc:
        return _simulation_error_response(exc, request_id)


@router.post("/start")
async def start_simulation(
    payload: StartSimulationRequest,
    response: Response,
    x_admin_key: str | None = Header(default=None, alias="X-Admin-Key"),
    request_id: str = Depends(request_id_header),
    db: AsyncSession = Depends(get_db),
):
    if error := mutation_auth_error(x_admin_key, request_id):
        return error
    return await _wrap(
        get_timeline_simulator().start(db, payload, request_id=request_id),
        response,
        request_id,
        "Simulation started",
    )


@router.post("/pause")
async def pause_simulation(
    response: Response,
    x_admin_key: str | None = Header(default=None, alias="X-Admin-Key"),
    request_id: str = Depends(request_id_header),
    db: AsyncSession = Depends(get_db),
):
    if error := mutation_auth_error(x_admin_key, request_id):
        return error
    return await _wrap(get_timeline_simulator().pause(db), response, request_id, "Simulation paused")


@router.post("/resume")
async def resume_simulation(
    response: Response,
    x_admin_key: str | None = Header(default=None, alias="X-Admin-Key"),
    request_id: str = Depends(request_id_header),
    db: AsyncSession = Depends(get_db),
):
    if error := mutation_auth_error(x_admin_key, request_id):
        return error
    return await _wrap(get_timeline_simulator().resume(db), response, request_id, "Simulation resumed")


@router.post("/reset")
async def reset_simulation(
    response: Response,
    payload: ResetSimulationRequest | None = None,
    x_admin_key: str | None = Header(default=None, alias="X-Admin-Key"),
    request_id: str = Depends(request_id_header),
    db: AsyncSession = Depends(get_db),
):
    if error := mutation_auth_error(x_admin_key, request_id):
        return error
    scenario_id = payload.scenario_id if payload else None
    return await _wrap(
        get_timeline_simulator().reset(db, scenario_id=scenario_id, request_id=request_id),
        response,
        request_id,
        "Simulation reset",
    )


@router.get("/status")
async def simulation_status(
    response: Response,
    request_id: str = Depends(request_id_header),
    db: AsyncSession = Depends(get_db),
):
    return await _wrap(get_timeline_simulator().status(db), response, request_id)


@router.post("/event")
async def inject_simulation_event(
    payload: JudgeEventRequest,
    response: Response,
    x_admin_key: str | None = Header(default=None, alias="X-Admin-Key"),
    request_id: str = Depends(request_id_header),
    db: AsyncSession = Depends(get_db),
):
    if error := mutation_auth_error(x_admin_key, request_id):
        return error
    return await _wrap(
        get_timeline_simulator().inject_event(db, payload, request_id=request_id),
        response,
        request_id,
        "Simulation event processed",
    )


@router.post("/advance")
async def advance_simulation(
    response: Response,
    x_admin_key: str | None = Header(default=None, alias="X-Admin-Key"),
    request_id: str = Depends(request_id_header),
    db: AsyncSession = Depends(get_db),
):
    if error := mutation_auth_error(x_admin_key, request_id):
        return error
    return await _wrap(
        get_timeline_simulator().advance(db, request_id=request_id),
        response,
        request_id,
        "Simulation advanced",
    )


@router.get("/events")
async def event_history(
    response: Response,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    simulation_id: str | None = Query(default=None),
    request_id: str = Depends(request_id_header),
    db: AsyncSession = Depends(get_db),
):
    data: EventHistoryData
    data = await get_timeline_simulator().list_event_history(
        db,
        page=page,
        page_size=page_size,
        simulation_id=simulation_id,
    )
    response.headers["X-Request-ID"] = request_id
    return success_response(data)


@router.get("/notifications")
async def notification_outbox(
    response: Response,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status: str | None = Query(default=None),
    request_id: str = Depends(request_id_header),
    db: AsyncSession = Depends(get_db),
):
    data: NotificationListData
    data = await get_timeline_simulator().list_notifications(db, page=page, page_size=page_size, status=status)
    response.headers["X-Request-ID"] = request_id
    return success_response(data)


@router.post("/notifications/{notification_id}/ack")
async def acknowledge_notification(
    notification_id: str,
    response: Response,
    x_admin_key: str | None = Header(default=None, alias="X-Admin-Key"),
    request_id: str = Depends(request_id_header),
    db: AsyncSession = Depends(get_db),
):
    if error := mutation_auth_error(x_admin_key, request_id):
        return error
    return await _wrap(
        get_timeline_simulator().acknowledge_notification(db, notification_id),
        response,
        request_id,
        "Simulation notification acknowledged",
    )
