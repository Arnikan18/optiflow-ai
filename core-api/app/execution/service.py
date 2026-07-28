import asyncio
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException

from app.adapters.tool_client import ToolClient
from app.execution.schemas import (
    ComponentVerification,
    ExecutionReceipt,
    ExecutionVerificationRequest,
    ExecutionVerificationResponse,
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


async def verify_execution(
    run_id: str,
    payload: ExecutionVerificationRequest,
    request_id: str | None = None,
) -> ExecutionVerificationResponse:
    client = ToolClient(request_id=request_id or run_id)
    checked_at = utc_now()

    workforce_task = client.verify_reservation(
        reservation_id=payload.reservation_id,
        expected_run_id=run_id,
        expected_incident_id=payload.incident_id,
        expected_specialist_id=payload.specialist_id,
    )
    incident_task = client.verify_incident_assignment(
        incident_id=payload.incident_id,
        expected_run_id=run_id,
        expected_specialist_id=payload.specialist_id,
    )
    communication_task = client.verify_assignment_request(
        assignment_request_id=payload.assignment_request_id,
        expected_run_id=run_id,
        expected_incident_id=payload.incident_id,
        expected_specialist_id=payload.specialist_id,
    )

    workforce_raw, incident_raw, communication_raw = await asyncio.gather(
        workforce_task,
        incident_task,
        communication_task,
        return_exceptions=True,
    )

    workforce = _component("workforce", workforce_raw)
    incident = _component("incident", incident_raw)
    communication = _component("communication", communication_raw)

    component_map = {
        "workforce": workforce,
        "incident": incident,
        "communication": communication,
    }
    overall_verified = all(item.verified for item in component_map.values())
    failed_components = [name for name, item in component_map.items() if not item.verified]
    recommended_next_state = _recommended_next_state(workforce, incident, communication, overall_verified)
    failed_checks = [
        f"{name}:{check}"
        for name, item in component_map.items()
        for check in item.failed_checks
    ]

    receipt = ExecutionReceipt(
        run_id=run_id,
        plan_id=payload.plan_id,
        profile_name=payload.profile_name,
        reservation_id=payload.reservation_id,
        assignment_request_id=payload.assignment_request_id,
        incident_id=payload.incident_id,
        specialist_id=payload.specialist_id,
        reservation_status=workforce.current_status,
        communication_status=communication.current_status,
        assignment_status=incident.assignment_status,
        overall_verified=overall_verified,
        verification_timestamp=checked_at,
        failed_checks=failed_checks,
        final_execution_state=recommended_next_state,
    )

    return ExecutionVerificationResponse(
        run_id=run_id,
        overall_verified=overall_verified,
        workforce_verification=workforce,
        incident_verification=incident,
        communication_verification=communication,
        failed_components=failed_components,
        checked_at=checked_at,
        recommended_next_state=recommended_next_state,
        execution_receipt=receipt,
    )


def _component(component_name: str, raw: Any) -> ComponentVerification:
    if isinstance(raw, Exception):
        return _unavailable_component(component_name, raw)
    if not isinstance(raw, dict):
        return ComponentVerification(
            verified=False,
            result="source_unavailable",
            failed_checks=["invalid_verification_response"],
            source_unavailable=True,
            error={"message": "Verification service returned a non-object response"},
        )
    return ComponentVerification(**raw)


def _unavailable_component(component_name: str, exc: Exception) -> ComponentVerification:
    status_code = getattr(exc, "status_code", None)
    detail: Any = getattr(exc, "detail", str(exc))
    if isinstance(exc, HTTPException):
        detail = exc.detail
    return ComponentVerification(
        verified=False,
        result="source_unavailable",
        failed_checks=["source_unavailable"],
        source_unavailable=True,
        error={
            "component": component_name,
            "status_code": status_code,
            "detail": detail,
        },
    )


def _recommended_next_state(
    workforce: ComponentVerification,
    incident: ComponentVerification,
    communication: ComponentVerification,
    overall_verified: bool,
) -> str:
    if overall_verified:
        return "COMPLETED"
    if any(item.source_unavailable for item in (workforce, incident, communication)):
        return "WAITING"
    if communication.result == "pending":
        return "WAITING"
    if communication.result in ("rejected", "expired"):
        return "REPLAN"
    if workforce.result == "pending" or incident.result == "pending":
        return "WAITING"
    if communication.current_status == "ACCEPTED" and workforce.result in ("not_found", "cancelled", "expired"):
        return "FAILED"
    if incident.result == "inconsistent":
        return "FAILED"
    if workforce.result == "inconsistent":
        return "FAILED"
    if "not_found" in {workforce.result, incident.result, communication.result}:
        return "FAILED"
    return "FAILED"
