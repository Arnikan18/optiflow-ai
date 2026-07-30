import json
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.database.models import Base
from app.simulation.enterprise_event_engine import EnterpriseEventEngine
from app.simulation.scenario_loader import ScenarioLoader
from app.simulation.schemas import (
    EventProcessingStatus,
    JudgeEventRequest,
    NotificationStatus,
    SimulationEventResult,
    StartSimulationRequest,
)
from app.simulation.timeline_simulator import TimelineSimulator


@pytest_asyncio.fixture()
async def session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as db:
        yield db
        await db.rollback()
    await engine.dispose()


class FakeClient:
    incidents = {
        "INC-1": {"incident_id": "INC-1", "priority": "MEDIUM", "status": "OPEN"},
        "INC-2": {"incident_id": "INC-2", "priority": "HIGH", "status": "IN_PROGRESS"},
    }
    specialists = {
        "SPEC-1": {"specialist_id": "SPEC-1", "availability": True},
    }
    created_incidents = []
    loaded_state = []

    def __init__(self, request_id):
        self.request_id = request_id

    async def load_initial_state(self, scenario_id, initial_state):
        self.loaded_state.append((scenario_id, len(initial_state.customers)))
        return {"scenario_id": scenario_id}

    async def get_customer(self, customer_id):
        if customer_id != "CUS-1":
            raise AssertionError("unexpected customer")
        return {"customer_id": customer_id}

    async def get_incident(self, incident_id):
        return self.incidents[incident_id]

    async def create_incident(self, payload):
        self.created_incidents.append(payload)
        self.incidents[payload["incident_id"]] = {**payload, "status": "OPEN"}
        return self.incidents[payload["incident_id"]]

    async def update_incident_fields(self, incident_id, payload):
        self.incidents[incident_id].update(payload)
        return self.incidents[incident_id]

    async def resolve_incident(self, incident_id, payload):
        self.incidents[incident_id]["status"] = "RESOLVED"
        return self.incidents[incident_id]

    async def get_specialist(self, specialist_id):
        return self.specialists[specialist_id]

    async def set_specialist_availability(self, specialist_id, available, reason):
        self.specialists[specialist_id]["availability"] = available
        return self.specialists[specialist_id]

    async def set_specialist_capacity(
        self,
        specialist_id,
        *,
        capacity,
        current_workload,
        reason,
    ):
        if capacity is not None:
            self.specialists[specialist_id]["capacity"] = capacity
        if current_workload is not None:
            self.specialists[specialist_id]["current_workload"] = current_workload
        return self.specialists[specialist_id]

    async def release_incident_workload(self, incident_id, reason):
        return {"incident_id": incident_id, "released_reservations": 1}


def _scenario(root: Path) -> ScenarioLoader:
    scenario_dir = root / "demo"
    scenario_dir.mkdir()
    metadata = {
        "scenario_id": "demo",
        "name": "Demo",
        "description": "Demo scenario",
        "version": "1.0.0",
        "mode": "TIMELINE",
        "duration": "1h",
        "start_time": "2026-07-22T09:00:00Z",
        "end_time": "2026-07-22T10:00:00Z",
        "timezone": "UTC",
        "stages": ["start"],
        "tags": ["test"],
        "schema_version": "1.0",
        "created_at": "2026-07-22T09:00:00Z",
    }
    initial = {"scenario_id": "demo", "customers": [{"customer_id": "CUS-1"}]}
    timeline = [
        {
            "event_id": "EVT-001",
            "scenario_id": "demo",
            "scheduled_time": "2026-07-22T09:15:00Z",
            "stage": "start",
            "event_type": "ENGINEER_ON_LEAVE",
            "payload": {"specialist_id": "SPEC-1", "reason": "test"},
            "description": "Specialist unavailable",
            "sequence": 1,
            "enabled": True,
        }
    ]
    (scenario_dir / "metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
    (scenario_dir / "initial_state.json").write_text(json.dumps(initial), encoding="utf-8")
    (scenario_dir / "timeline.json").write_text(json.dumps(timeline), encoding="utf-8")
    return ScenarioLoader(root, default_scenario_id="demo")


@pytest.mark.asyncio
async def test_event_engine_new_ticket_idempotent_retry(session):
    FakeClient.incidents = {"INC-1": {"incident_id": "INC-1", "priority": "MEDIUM", "status": "OPEN"}}
    FakeClient.created_incidents = []
    engine = EnterpriseEventEngine(client_factory=FakeClient)
    request = JudgeEventRequest(
        event_id="EVT-NEW",
        event_type="NEW_TICKET",
        scenario_id="demo",
        idempotency_key="idem-new",
        payload={
            "incident_id": "INC-NEW",
            "customer_id": "CUS-1",
            "title": "New incident",
            "description": "New incident description",
            "priority": "HIGH",
            "sla_deadline": "2026-07-22T11:00:00Z",
            "required_skills": ["security", "integration"],
        },
    )

    first = await engine.process_event(
        session,
        request,
        simulation_id="SIM-1",
        request_id="REQ-1",
        current_stage="start",
        current_simulation_time=None,
    )
    second = await engine.process_event(
        session,
        request,
        simulation_id="SIM-1",
        request_id="REQ-1",
        current_stage="start",
        current_simulation_time=None,
    )

    assert first.processing_status == EventProcessingStatus.APPLIED
    assert first.notification_status == NotificationStatus.PENDING
    assert second.event_id == first.event_id
    assert len(FakeClient.created_incidents) == 1
    assert FakeClient.created_incidents[0]["required_skills"] == ["security", "integration"]


@pytest.mark.asyncio
async def test_event_engine_rejects_non_meaningful_priority_escalation(session):
    engine = EnterpriseEventEngine(client_factory=FakeClient)
    request = JudgeEventRequest(
        event_id="EVT-BAD-PRIORITY",
        event_type="ESCALATE_PRIORITY",
        payload={"incident_id": "INC-1", "new_priority": "LOW"},
    )

    result = await engine.process_event(
        session,
        request,
        simulation_id="SIM-1",
        request_id="REQ-1",
        current_stage=None,
        current_simulation_time=None,
    )

    assert result.accepted is False
    assert result.processing_status == EventProcessingStatus.FAILED
    assert result.errors[0]["error_code"] == "SIMULATION_PRIORITY_NOT_ESCALATED"


@pytest.mark.asyncio
async def test_event_engine_changes_worker_capacity(session):
    FakeClient.specialists = {
        "SPEC-1": {
            "specialist_id": "SPEC-1",
            "availability": True,
            "capacity": 3,
            "current_workload": 1,
        }
    }
    engine = EnterpriseEventEngine(client_factory=FakeClient)
    request = JudgeEventRequest(
        event_id="EVT-WORKER-CAPACITY",
        event_type="CHANGE_WORKER_CAPACITY",
        payload={
            "specialist_id": "SPEC-1",
            "capacity": 4,
            "current_workload": 3,
            "reason": "Judge changed the live team load",
        },
    )

    result = await engine.process_event(
        session,
        request,
        simulation_id="SIM-1",
        request_id="REQ-1",
        current_stage=None,
        current_simulation_time=None,
    )

    assert result.accepted is True
    assert result.changed_entities[0]["change"] == "worker_capacity_changed"
    assert FakeClient.specialists["SPEC-1"]["capacity"] == 4
    assert FakeClient.specialists["SPEC-1"]["current_workload"] == 3


@pytest.mark.asyncio
async def test_timeline_simulator_start_pause_resume_advance_complete(session, tmp_path):
    FakeClient.specialists = {"SPEC-1": {"specialist_id": "SPEC-1", "availability": True}}
    loader = _scenario(tmp_path)
    engine = EnterpriseEventEngine(client_factory=FakeClient)
    simulator = TimelineSimulator(loader=loader, event_engine=engine)

    started = await simulator.start(session, StartSimulationRequest(scenario_id="demo"), request_id="REQ-START")
    paused = await simulator.pause(session)
    resumed = await simulator.resume(session)
    advanced = await simulator.advance(session, request_id="REQ-ADV")

    assert started.status == "RUNNING"
    assert paused.status == "PAUSED"
    assert resumed.status == "RUNNING"
    assert advanced.completed is True
    assert advanced.status == "COMPLETED"
    assert advanced.processed_events == ["EVT-001"]
    assert FakeClient.specialists["SPEC-1"]["availability"] is False


@pytest.mark.asyncio
async def test_timeline_simulator_duplicate_start_rejected(session, tmp_path):
    simulator = TimelineSimulator(
        loader=_scenario(tmp_path),
        event_engine=EnterpriseEventEngine(client_factory=FakeClient),
    )

    await simulator.start(session, StartSimulationRequest(scenario_id="demo"), request_id="REQ-START")

    with pytest.raises(Exception) as exc:
        await simulator.start(session, StartSimulationRequest(scenario_id="demo"), request_id="REQ-START-2")

    assert getattr(exc.value, "error_code") == "SIMULATION_ALREADY_RUNNING"
