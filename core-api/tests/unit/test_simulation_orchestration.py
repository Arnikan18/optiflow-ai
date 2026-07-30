import pytest
from app.services.enterprise_monitor import EnterpriseMonitor
from app.services.simulation_coordinator import SimulationCoordinator

def test_enterprise_monitor_no_baseline():
    """Verify monitor triggers replan if baseline snapshot is missing."""
    assert EnterpriseMonitor.should_replan(
        event=None,
        baseline_snapshot=None,
        current_state={"incidents": [], "specialists": []}
    ) is True

def test_enterprise_monitor_event_replan_rules():
    """Verify event-specific replanning decision rules."""
    baseline = {"incidents": [], "specialists": []}
    current = {"incidents": [], "specialists": []}

    # 1. Critical new ticket -> True
    assert EnterpriseMonitor.should_replan(
        event={"event_type": "NEW_TICKET", "priority": "CRITICAL"},
        baseline_snapshot=baseline,
        current_state=current
    ) is True

    # 2. Low new ticket -> False
    assert EnterpriseMonitor.should_replan(
        event={"event_type": "NEW_TICKET", "priority": "LOW"},
        baseline_snapshot=baseline,
        current_state=current
    ) is False

    # 3. Priority escalated -> True
    assert EnterpriseMonitor.should_replan(
        event={"event_type": "PRIORITY_ESCALATED"},
        baseline_snapshot=baseline,
        current_state=current
    ) is True

    # 4. Comment added -> False
    assert EnterpriseMonitor.should_replan(
        event={"event_type": "COMMENT_ADDED"},
        baseline_snapshot=baseline,
        current_state=current
    ) is False

def test_enterprise_monitor_snapshot_fallback():
    """Verify snapshot diff fallback logic when event metadata is absent."""
    baseline = {
        "incidents": [{"incident_id": "INC-1", "priority": "LOW", "status": "OPEN"}],
        "specialists": [{"specialist_id": "SPEC-1", "active": True}]
    }

    # 1. No changes -> False
    current_no_change = {
        "incidents": [{"incident_id": "INC-1", "priority": "LOW", "status": "OPEN"}],
        "specialists": [{"specialist_id": "SPEC-1", "active": True}]
    }
    assert EnterpriseMonitor.should_replan(
        event=None,
        baseline_snapshot=baseline,
        current_state=current_no_change
    ) is False

    # 2. Priority changed -> True
    current_priority_change = {
        "incidents": [{"incident_id": "INC-1", "priority": "HIGH", "status": "OPEN"}],
        "specialists": [{"specialist_id": "SPEC-1", "active": True}]
    }
    assert EnterpriseMonitor.should_replan(
        event=None,
        baseline_snapshot=baseline,
        current_state=current_priority_change
    ) is True

    # 3. Specialist active state changed -> True
    current_spec_change = {
        "incidents": [{"incident_id": "INC-1", "priority": "LOW", "status": "OPEN"}],
        "specialists": [{"specialist_id": "SPEC-1", "active": False}]
    }
    assert EnterpriseMonitor.should_replan(
        event=None,
        baseline_snapshot=baseline,
        current_state=current_spec_change
    ) is True

class DummyNotifier:
    def __init__(self):
        self.started_calls = []
        self.change_calls = []
        self.complete_calls = []

    async def on_simulation_started(self, scenario_id: str, mode: str) -> None:
        self.started_calls.append((scenario_id, mode))

    async def on_enterprise_change(self, event: dict, state: dict) -> None:
        self.change_calls.append((event, state))

    async def on_execution_complete(self, run_id: str, pos: int, state: dict) -> None:
        self.complete_calls.append((run_id, pos, state))

@pytest.mark.anyio
async def test_simulation_coordinator_notifier():
    """Verify SimulationCoordinator triggers registered notifier callbacks."""
    notifier = DummyNotifier()
    SimulationCoordinator.register_notifier(notifier)

    # 1. Started
    await SimulationCoordinator.on_simulation_started("scen-1", "Timeline")
    assert notifier.started_calls == [("scen-1", "Timeline")]

    # 2. Change
    await SimulationCoordinator.on_enterprise_change({"type": "NEW_TICKET"}, {"data": 1})
    assert notifier.change_calls == [({"type": "NEW_TICKET"}, {"data": 1})]

    # 3. Complete
    await SimulationCoordinator.on_execution_complete("run-1", 2, {"state": 3})
    assert notifier.complete_calls == [("run-1", 2, {"state": 3})]

def test_graph_compilation_and_node():
    """Verify that the StateGraph compiles successfully and contains the monitor node."""
    from app.agent.graph import compiled_graph
    
    # Check that nodes exist
    nodes = compiled_graph.nodes
    assert "enterprise_monitor" in nodes
    assert "decision_intelligence" in nodes
    assert compiled_graph.get_graph() is not None

def test_route_after_monitoring():
    """Verify routing logic from the enterprise monitor node."""
    from app.agent.graph import route_after_monitoring
    
    # 1. No simulation mode active -> routes to evaluate_quality (default entry point)
    state_no_sim = {"simulation_mode": None}
    assert route_after_monitoring(state_no_sim) == "evaluate_quality"
    
    # 2. Simulation mode active, replan_needed=True -> routes to evaluate_quality
    state_replan = {"simulation_mode": "Timeline", "replan_needed": True}
    assert route_after_monitoring(state_replan) == "evaluate_quality"
    
    # 3. Simulation mode active, replan_needed=False -> routes to complete_run (skip planning)
    state_skip = {"simulation_mode": "Timeline", "replan_needed": False}
    assert route_after_monitoring(state_skip) == "complete_run"

    # 4. Simulation mode active, replan_needed=False but status is REPLANNING -> routes to evaluate_quality
    state_loop = {"simulation_mode": "Timeline", "replan_needed": False, "status": "REPLANNING"}
    assert route_after_monitoring(state_loop) == "evaluate_quality"


@pytest.mark.anyio
async def test_complete_run_lifecycle_handling():
    """Verify baseline update and simulation notifications on successful execution."""
    from app.agent.nodes.complete_run import complete_run
    
    # Reset coordinator notifier
    notifier = DummyNotifier()
    SimulationCoordinator.register_notifier(notifier)
    
    import unittest.mock as mock
    with mock.patch("app.database.persistence.save_agent_run") as mock_save_run, \
         mock.patch("app.database.persistence.save_graph_checkpoint") as mock_save_cp, \
         mock.patch("app.database.persistence.save_run_event") as mock_save_ev:
         
        # Scenario A: Successful Execution (Approved + Executed)
        state_success = {
            "run_id": "RUN-SUCCESS",
            "approval_status": "APPROVED",
            "status": "EXECUTED",
            "timeline_position": 4,
            "enterprise_state": {"incidents": [1]}
        }
        res = await complete_run(state_success)
        assert res == {"status": "COMPLETED"}
        # Baseline snapshot must be updated in state
        assert state_success.get("baseline_enterprise_snapshot") == {"incidents": [1]}
        # Coordinator must be notified once with the lightweight payload DTO
        expected_payload = {
            "run_id": "RUN-SUCCESS",
            "scenario_id": None,
            "timeline_position": 4,
            "simulation_time": None,
            "status": "EXECUTED"
        }
        assert notifier.complete_calls == [("RUN-SUCCESS", 4, expected_payload)]
        
        # Scenario B: Rejected Recommendation
        notifier.complete_calls.clear()
        state_rejected = {
            "run_id": "RUN-REJECT",
            "approval_status": "REJECTED",
            "status": "FAILED_SAFE",
            "timeline_position": 4,
            "enterprise_state": {"incidents": [1]}
        }
        await complete_run(state_rejected)
        # Baseline snapshot must NOT be updated
        assert "baseline_enterprise_snapshot" not in state_rejected
        # Coordinator must NOT be notified
        assert len(notifier.complete_calls) == 0

        # Scenario C: SAGA execution failure
        notifier.complete_calls.clear()
        state_saga_fail = {
            "run_id": "RUN-SAGA-FAIL",
            "approval_status": "APPROVED",
            "status": "FAILED_SAGA",
            "timeline_position": 4,
            "enterprise_state": {"incidents": [1]}
        }
        await complete_run(state_saga_fail)
        # Baseline snapshot must NOT be updated
        assert "baseline_enterprise_snapshot" not in state_saga_fail
        # Coordinator must NOT be notified
        assert len(notifier.complete_calls) == 0


class FailingNotifier:
    async def on_execution_complete(self, run_id: str, pos: int, state: dict) -> None:
        raise ValueError("Simulated network outage")


@pytest.mark.anyio
async def test_notifier_failure_does_not_fail_run():
    """Verify that exceptions thrown by the simulation notifier do not fail the run completion."""
    from app.agent.nodes.complete_run import complete_run
    
    SimulationCoordinator.register_notifier(FailingNotifier())
    
    import unittest.mock as mock
    with mock.patch("app.database.persistence.save_agent_run"), \
         mock.patch("app.database.persistence.save_graph_checkpoint"), \
         mock.patch("app.database.persistence.save_run_event"):
         
        state = {
            "run_id": "RUN-FAILING-NOTIFIER",
            "approval_status": "APPROVED",
            "status": "EXECUTED",
            "timeline_position": 5,
            "enterprise_state": {"data": True}
        }
        # Call node: must complete successfully without raising exception
        res = await complete_run(state)
        assert res == {"status": "COMPLETED"}
        assert state.get("baseline_enterprise_snapshot") == {"data": True}



