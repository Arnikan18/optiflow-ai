from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import settings
from app.demo.schemas import DemoResetRequest, FailureSimulationRequest, SpecialistResponseSimulationRequest
from app.demo.service import (
    configure_failure,
    get_demo_health,
    get_demo_portfolio,
    get_simulation_state,
    queue_specialist_response,
    reset_demo,
)
from app.main_dependencies import get_db


router = APIRouter(prefix="/api/v1/demo", tags=["demo"])
legacy_router = APIRouter(prefix="/api/demo", tags=["demo"])


def success_response(data: Any, message: str = "Request completed successfully") -> dict[str, Any]:
    from app.demo.service import utc_timestamp

    return {
        "success": True,
        "message": message,
        "timestamp": utc_timestamp(),
        "data": data,
    }


def request_id_header(x_request_id: str | None = Header(default=None, alias="X-Request-ID")) -> str:
    return x_request_id.strip() if x_request_id and x_request_id.strip() else str(uuid4())


def require_demo_mode() -> None:
    if not settings.demo_mode:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Demo mode is disabled")


def wrapped(data: Any, response: Response, request_id: str) -> dict[str, Any]:
    response.headers["X-Request-ID"] = request_id
    return success_response(data)


@router.get("/portfolio")
async def demo_portfolio(
    response: Response,
    request_id: str = Depends(request_id_header),
):
    return wrapped((await get_demo_portfolio(request_id)).model_dump(mode="json"), response, request_id)


@legacy_router.get("/portfolio", deprecated=True)
async def legacy_demo_portfolio(
    response: Response,
    request_id: str = Depends(request_id_header),
):
    return wrapped((await get_demo_portfolio(request_id)).model_dump(mode="json"), response, request_id)


@router.get("/health")
async def demo_health(
    response: Response,
    request_id: str = Depends(request_id_header),
    db: AsyncSession = Depends(get_db),
):
    return wrapped((await get_demo_health(db, request_id)).model_dump(mode="json"), response, request_id)


@router.post("/simulation/specialist-response", dependencies=[Depends(require_demo_mode)])
async def demo_specialist_response(
    payload: SpecialistResponseSimulationRequest,
    response: Response,
    request_id: str = Depends(request_id_header),
):
    return wrapped(await queue_specialist_response(payload, request_id), response, request_id)


@router.post("/simulation/failure", dependencies=[Depends(require_demo_mode)])
async def demo_failure(
    payload: FailureSimulationRequest,
    response: Response,
    request_id: str = Depends(request_id_header),
):
    if not settings.demo_allow_failure_injection:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Failure injection is disabled")
    return wrapped(await configure_failure(payload, request_id), response, request_id)


@router.post("/simulation/reset", dependencies=[Depends(require_demo_mode)])
async def demo_reset(
    response: Response,
    payload: DemoResetRequest | None = None,
    request_id: str = Depends(request_id_header),
):
    return wrapped(await reset_demo(payload, request_id), response, request_id)


@router.get("/simulation/state", dependencies=[Depends(require_demo_mode)])
async def demo_simulation_state(
    response: Response,
    request_id: str = Depends(request_id_header),
):
    return wrapped((await get_simulation_state(request_id)).model_dump(mode="json"), response, request_id)
