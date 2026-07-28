from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Header, Response

from app.execution.schemas import ExecutionVerificationRequest
from app.execution.service import verify_execution


router = APIRouter(prefix="/api/v1/runs", tags=["execution-verification"])


def request_id_header(x_request_id: str | None = Header(default=None, alias="X-Request-ID")) -> str:
    return x_request_id.strip() if x_request_id and x_request_id.strip() else str(uuid4())


@router.post("/{run_id}/execution/verify")
async def verify_run_execution(
    run_id: str,
    payload: ExecutionVerificationRequest,
    response: Response,
    request_id: str | None = Header(default=None, alias="X-Request-ID"),
) -> dict[str, Any]:
    effective_request_id = request_id_header(request_id)
    response.headers["X-Request-ID"] = effective_request_id
    result = await verify_execution(run_id.strip().upper(), payload, request_id=effective_request_id)
    return result.model_dump(mode="json")
