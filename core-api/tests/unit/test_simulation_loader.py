import json
from pathlib import Path

import pytest

from app.simulation.scenario_loader import ScenarioLoader
from app.simulation.schemas import SimulationError


def _metadata(**overrides):
    data = {
        "scenario_id": "demo",
        "name": "Demo",
        "description": "Demo scenario",
        "version": "1.0.0",
        "mode": "TIMELINE",
        "duration": "1h",
        "start_time": "2026-07-22T09:00:00Z",
        "end_time": "2026-07-22T10:00:00Z",
        "timezone": "UTC",
        "stages": ["start", "middle"],
        "tags": ["test"],
        "schema_version": "1.0",
        "created_at": "2026-07-22T09:00:00Z",
    }
    data.update(overrides)
    return data


def _initial(**overrides):
    data = {
        "scenario_id": "demo",
        "customers": [],
        "specialists": [],
        "incidents": [],
        "assignments": [],
        "reservations": [],
        "notifications": [],
        "workloads": [],
        "sla_data": [],
        "supporting_data": {},
    }
    data.update(overrides)
    return data


def _timeline(**overrides):
    event = {
        "event_id": "EVT-001",
        "scenario_id": "demo",
        "scheduled_time": "2026-07-22T09:15:00Z",
        "stage": "start",
        "event_type": "NEW_TICKET",
        "payload": {
            "incident_id": "INC-1",
            "customer_id": "CUS-1",
            "title": "Test",
            "description": "Test incident",
            "priority": "HIGH",
            "sla_deadline": "2026-07-22T11:00:00Z",
        },
        "description": "Create a ticket",
        "sequence": 1,
        "enabled": True,
    }
    event.update(overrides)
    return [event]


def _write_scenario(root: Path, folder: str = "demo", *, metadata=None, initial=None, timeline=None) -> Path:
    scenario_dir = root / folder
    scenario_dir.mkdir()
    (scenario_dir / "metadata.json").write_text(json.dumps(metadata or _metadata()), encoding="utf-8")
    (scenario_dir / "initial_state.json").write_text(json.dumps(initial or _initial()), encoding="utf-8")
    (scenario_dir / "timeline.json").write_text(json.dumps(timeline or _timeline()), encoding="utf-8")
    return scenario_dir


def test_loader_discovers_valid_scenario(tmp_path):
    _write_scenario(tmp_path)
    loader = ScenarioLoader(tmp_path, default_scenario_id="demo")

    listed = loader.list_scenarios()
    loaded = loader.load_scenario("demo")

    assert listed.default_scenario_id == "demo"
    assert listed.scenarios[0].scenario_id == "demo"
    assert loaded.metadata.name == "Demo"
    assert loaded.timeline[0].event_type == "NEW_TICKET"


def test_loader_rejects_missing_required_file(tmp_path):
    scenario_dir = tmp_path / "broken"
    scenario_dir.mkdir()
    (scenario_dir / "initial_state.json").write_text(json.dumps(_initial()), encoding="utf-8")

    with pytest.raises(SimulationError) as exc:
        ScenarioLoader(tmp_path).list_scenarios()

    assert exc.value.error_code == "SIMULATION_SCENARIO_INCOMPLETE"


def test_loader_rejects_malformed_json(tmp_path):
    scenario_dir = _write_scenario(tmp_path)
    (scenario_dir / "timeline.json").write_text("{", encoding="utf-8")

    with pytest.raises(SimulationError) as exc:
        ScenarioLoader(tmp_path).load_scenario("demo")

    assert exc.value.error_code == "SIMULATION_SCENARIO_JSON_INVALID"


def test_loader_rejects_duplicate_event_id_and_bad_order(tmp_path):
    timeline = _timeline() + _timeline(sequence=2)
    _write_scenario(tmp_path, timeline=timeline)

    with pytest.raises(SimulationError) as exc:
        ScenarioLoader(tmp_path).load_scenario("demo")

    assert exc.value.error_code == "SIMULATION_SCENARIO_INVALID"
    assert "duplicate event_id" in exc.value.details[0]["message"]


def test_loader_rejects_unsupported_event_type(tmp_path):
    _write_scenario(tmp_path, timeline=_timeline(event_type="BAD_EVENT"))

    with pytest.raises(SimulationError) as exc:
        ScenarioLoader(tmp_path).load_scenario("demo")

    assert exc.value.error_code == "SIMULATION_SCENARIO_INVALID"


def test_loader_rejects_duplicate_scenario_ids(tmp_path):
    _write_scenario(tmp_path, "demo-a")
    _write_scenario(tmp_path, "demo-b")

    with pytest.raises(SimulationError) as exc:
        ScenarioLoader(tmp_path).list_scenarios()

    assert exc.value.error_code == "SIMULATION_DUPLICATE_SCENARIO_ID"
