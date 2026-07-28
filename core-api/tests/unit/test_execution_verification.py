import pytest
from fastapi import HTTPException

from app.execution.schemas import ExecutionVerificationRequest
from app.execution import service as execution_service


def verification_request(**overrides):
    payload = {
        "reservation_id": "RES-VERIFY-001",
        "incident_id": "INC-VERIFY-001",
        "specialist_id": "SPEC-MAYA",
        "assignment_request_id": "AR-VERIFY-001",
        "plan_id": "PLAN-BALANCED",
        "profile_name": "Balanced",
    }
    payload.update(overrides)
    return ExecutionVerificationRequest(**payload)


class FakeToolClient:
    def __init__(self, *, workforce, incident, communication):
        self.workforce = workforce
        self.incident = incident
        self.communication = communication

    async def verify_reservation(self, **_kwargs):
        if isinstance(self.workforce, Exception):
            raise self.workforce
        return self.workforce

    async def verify_incident_assignment(self, **_kwargs):
        if isinstance(self.incident, Exception):
            raise self.incident
        return self.incident

    async def verify_assignment_request(self, **_kwargs):
        if isinstance(self.communication, Exception):
            raise self.communication
        return self.communication


def install_fake_client(monkeypatch, fake_client):
    monkeypatch.setattr(execution_service, "ToolClient", lambda request_id=None: fake_client)


def workforce_result(**overrides):
    payload = {
        "verified": True,
        "result": "verified",
        "reservation_id": "RES-VERIFY-001",
        "expected_values": {},
        "actual_values": {"status": "CONFIRMED"},
        "failed_checks": [],
        "checked_at": "2026-07-29T00:00:00Z",
        "current_status": "CONFIRMED",
    }
    payload.update(overrides)
    return payload


def incident_result(**overrides):
    payload = {
        "verified": True,
        "result": "verified",
        "incident_id": "INC-VERIFY-001",
        "expected_values": {},
        "actual_values": {"assigned_specialist_id": "SPEC-MAYA"},
        "failed_checks": [],
        "checked_at": "2026-07-29T00:00:00Z",
        "assignment_status": "active",
    }
    payload.update(overrides)
    return payload


def communication_result(**overrides):
    payload = {
        "verified": True,
        "result": "verified",
        "assignment_request_id": "AR-VERIFY-001",
        "expected_values": {},
        "actual_values": {"status": "ACCEPTED"},
        "failed_checks": [],
        "checked_at": "2026-07-29T00:00:00Z",
        "current_status": "ACCEPTED",
    }
    payload.update(overrides)
    return payload


@pytest.mark.asyncio
async def test_execution_verification_all_verified(monkeypatch):
    install_fake_client(
        monkeypatch,
        FakeToolClient(
            workforce=workforce_result(),
            incident=incident_result(),
            communication=communication_result(),
        ),
    )

    result = await execution_service.verify_execution("RUN-VERIFY-001", verification_request(), request_id="REQ-1")

    assert result.overall_verified is True
    assert result.recommended_next_state == "COMPLETED"
    assert result.failed_components == []
    assert result.execution_receipt.final_execution_state == "COMPLETED"
    assert result.execution_receipt.reservation_status == "CONFIRMED"
    assert result.execution_receipt.communication_status == "ACCEPTED"


@pytest.mark.asyncio
async def test_execution_verification_pending_communication_waits(monkeypatch):
    install_fake_client(
        monkeypatch,
        FakeToolClient(
            workforce=workforce_result(),
            incident=incident_result(),
            communication=communication_result(
                verified=False,
                result="pending",
                failed_checks=["request_pending"],
                current_status="PENDING",
                actual_values={"status": "PENDING"},
            ),
        ),
    )

    result = await execution_service.verify_execution("RUN-VERIFY-001", verification_request())

    assert result.overall_verified is False
    assert result.failed_components == ["communication"]
    assert result.recommended_next_state == "WAITING"
    assert "communication:request_pending" in result.execution_receipt.failed_checks


@pytest.mark.asyncio
async def test_execution_verification_rejected_communication_replans(monkeypatch):
    install_fake_client(
        monkeypatch,
        FakeToolClient(
            workforce=workforce_result(),
            incident=incident_result(),
            communication=communication_result(
                verified=False,
                result="rejected",
                failed_checks=["request_rejected"],
                current_status="REJECTED",
                actual_values={"status": "REJECTED"},
            ),
        ),
    )

    result = await execution_service.verify_execution("RUN-VERIFY-001", verification_request())

    assert result.recommended_next_state == "REPLAN"
    assert result.execution_receipt.final_execution_state == "REPLAN"


@pytest.mark.asyncio
async def test_execution_verification_source_unavailable_waits(monkeypatch):
    install_fake_client(
        monkeypatch,
        FakeToolClient(
            workforce=HTTPException(status_code=503, detail={"message": "workforce unavailable"}),
            incident=incident_result(),
            communication=communication_result(),
        ),
    )

    result = await execution_service.verify_execution("RUN-VERIFY-001", verification_request())

    assert result.overall_verified is False
    assert result.workforce_verification.source_unavailable is True
    assert result.recommended_next_state == "WAITING"
    assert "workforce" in result.failed_components
