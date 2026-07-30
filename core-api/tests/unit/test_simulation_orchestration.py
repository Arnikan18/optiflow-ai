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
         
        state_success = {
            "run_id": "RUN-SUCCESS",
            "approval_status": "APPROVED",
            "status": "EXECUTED",
            "timeline_position": 4,
            "enterprise_state": {"incidents": [1]}
        }
        res = await complete_run(state_success)
        assert res.get("status") == "COMPLETED"
        assert res.get("baseline_enterprise_snapshot") == {"incidents": [1]}
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
        assert res.get("status") == "COMPLETED"
        assert res.get("baseline_enterprise_snapshot") == {"data": True}
        assert state.get("baseline_enterprise_snapshot") == {"data": True}


@pytest.mark.anyio
async def test_complete_run_persistence_verification():
    """Regression test verifying LangGraph state updates during complete_run."""
    from langgraph.graph import StateGraph
    from app.agent.state import AgentState
    from app.agent.nodes.complete_run import complete_run
    import unittest.mock as mock

    builder = StateGraph(AgentState)
    builder.add_node("complete_run", complete_run)
    builder.set_entry_point("complete_run")
    builder.set_finish_point("complete_run")
    graph = builder.compile()

    state = {
        "run_id": "RUN-TEST-PERSISTENCE",
        "approval_status": "APPROVED",
        "status": "EXECUTED",
        "timeline_position": 4,
        "enterprise_state": {"incidents": [1]}
    }

    with mock.patch("app.database.persistence.save_agent_run"), \
         mock.patch("app.database.persistence.save_graph_checkpoint"), \
         mock.patch("app.database.persistence.save_run_event"):
         
        final_state = await graph.ainvoke(state)
        snapshot = final_state.get("baseline_enterprise_snapshot")
        print(f"\n[PERSISTENCE TEST] Resulting snapshot: {snapshot}")
        assert snapshot == {"incidents": [1]}


@pytest.mark.anyio
async def test_compiled_graph_replan_routing_loop():
    """Verify that a critical event triggers replanning, runs optimizer, DI, and pauses for approval."""
    from app.agent.graph import compiled_graph
    from optiflow_shared.tool_contracts import StructuredGoal, TimeHorizon
    import unittest.mock as mock

    initial_state = {
        "run_id": "RUN-CRITICAL-TEST",
        "simulation_mode": "Timeline",
        "replan_needed": True,
        "status": "RECEIVED",
        "goal_text": "Optimize SLA and renewals"
    }

    mock_goal = StructuredGoal(
        summary="Optimize SLA and renewals",
        objectives=["SLA_PROTECTION", "RENEWAL_PROTECTION"],
        time_horizon=TimeHorizon(value=7, unit="DAYS"),
        hard_constraints=[],
        soft_preferences=[],
        requested_actions=[],
        ambiguities=[],
        unsupported_requests=[],
        interpretation_notes=["Mocked for graph integration routing"]
    )

    with mock.patch("app.agent.nodes.interpret_goal.interpret_goal_text", return_value=mock_goal), \
         mock.patch("app.database.persistence.save_agent_run"), \
         mock.patch("app.database.persistence.save_graph_checkpoint"), \
         mock.patch("app.database.persistence.save_run_event"):

        final_state = await compiled_graph.ainvoke(initial_state)

        # 1. Assert observable state transitions
        assert final_state["run_id"] == "RUN-CRITICAL-TEST"
        assert final_state["status"] == "WAITING_FOR_APPROVAL"  # Paused at human gate
        assert final_state["replan_needed"] is True

        # 2. Verify that optimization was executed
        assert final_state.get("candidate_plans") is not None
        assert len(final_state["candidate_plans"]) > 0
        assert final_state.get("recommended_plan") is not None

        # 3. Verify Decision Intelligence generated explanation DTO and presentation summaries
        assert final_state.get("decision_explanation") is not None
        assert final_state.get("business_summary") is not None
        assert final_state.get("change_summary") is not None
        assert len(final_state.get("decision_history", [])) == 1


@pytest.mark.anyio
async def test_compiled_graph_shortcut_routing_loop():
    """Verify that a non-critical event bypasses planning/optimizer/approval and completes directly."""
    from app.agent.graph import compiled_graph
    from optiflow_shared.tool_contracts import StructuredGoal, TimeHorizon
    import unittest.mock as mock

    initial_state = {
        "run_id": "RUN-SHORTCUT-TEST",
        "simulation_mode": "Timeline",
        "replan_needed": False,
        "status": "RECEIVED",
        "goal_text": "Optimize SLA and renewals",
        "recommended_plan": {"plan_id": "plan-pre-existing", "profile": "Balanced"},
        "candidate_plans": [{"plan_id": "plan-pre-existing", "profile": "Balanced"}],
        "decision_explanation": {"id": "old-explanation"},
        "decision_history": [{"id": "old-explanation"}],
        "business_summary": "old-business-summary",
        "change_summary": "old-change-summary",
        "baseline_enterprise_snapshot": {"incidents": [], "specialists": []},
        "latest_event": {"event_type": "COMMENT_ADDED"}
    }

    mock_goal = StructuredGoal(
        summary="Optimize SLA and renewals",
        objectives=["SLA_PROTECTION", "RENEWAL_PROTECTION"],
        time_horizon=TimeHorizon(value=7, unit="DAYS"),
        hard_constraints=[],
        soft_preferences=[],
        requested_actions=[],
        ambiguities=[],
        unsupported_requests=[],
        interpretation_notes=["Mocked for graph integration routing"]
    )

    import copy
    history_before_run = copy.deepcopy(initial_state["decision_history"])

    with mock.patch("app.agent.nodes.interpret_goal.interpret_goal_text", return_value=mock_goal), \
         mock.patch("app.database.persistence.save_agent_run"), \
         mock.patch("app.database.persistence.save_graph_checkpoint"), \
         mock.patch("app.database.persistence.save_run_event"):

        final_state = await compiled_graph.ainvoke(initial_state)

        # 1. Assert observable state transitions
        assert final_state["run_id"] == "RUN-SHORTCUT-TEST"
        assert final_state["status"] == "COMPLETED"  # Completed directly (reaches complete_run)
        assert final_state["replan_needed"] is False

        # 2. Verify optimization was skipped (previous recommendations remain unchanged)
        assert final_state["recommended_plan"] == {"plan_id": "plan-pre-existing", "profile": "Balanced"}
        assert final_state["candidate_plans"] == [{"plan_id": "plan-pre-existing", "profile": "Balanced"}]

        # 3. Verify Decision Intelligence was skipped (no new snapshots in history)
        assert final_state["decision_explanation"] == {"id": "old-explanation"}
        assert final_state["business_summary"] == "old-business-summary"
        assert final_state["change_summary"] == "old-change-summary"
        assert len(final_state["decision_history"]) == 1
        assert final_state["decision_history"] == history_before_run


@pytest.mark.anyio
async def test_scenario_new_ticket_event_replan():
    """Verify NEW_TICKET triggers replan only if priority is critical/high."""
    from app.agent.graph import compiled_graph
    from optiflow_shared.tool_contracts import StructuredGoal, TimeHorizon
    import unittest.mock as mock

    mock_goal = StructuredGoal(
        summary="SLA Run", objectives=["SLA_PROTECTION"],
        time_horizon=TimeHorizon(value=7, unit="DAYS"),
        hard_constraints=[], soft_preferences=[], requested_actions=[], ambiguities=[], unsupported_requests=[],
        interpretation_notes=[]
    )

    # Case A: Low Priority -> No Replan
    state_low = {
        "run_id": "RUN-LOW",
        "simulation_mode": "Timeline",
        "status": "RECEIVED",
        "goal_text": "Optimize",
        "baseline_enterprise_snapshot": {"incidents": [], "specialists": []},
        "latest_event": {"event_type": "NEW_TICKET", "priority": "LOW"}
    }

    with mock.patch("app.agent.nodes.interpret_goal.interpret_goal_text", return_value=mock_goal), \
         mock.patch("app.database.persistence.save_agent_run"), \
         mock.patch("app.database.persistence.save_graph_checkpoint"), \
         mock.patch("app.database.persistence.save_run_event"):

        res_low = await compiled_graph.ainvoke(state_low)
        assert res_low["replan_needed"] is False
        assert res_low["status"] == "COMPLETED"

    # Case B: Critical Priority -> Replan
    state_crit = {
        "run_id": "RUN-CRIT",
        "simulation_mode": "Timeline",
        "status": "RECEIVED",
        "goal_text": "Optimize",
        "baseline_enterprise_snapshot": {"incidents": [], "specialists": []},
        "latest_event": {"event_type": "NEW_TICKET", "priority": "CRITICAL"}
    }

    with mock.patch("app.agent.nodes.interpret_goal.interpret_goal_text", return_value=mock_goal), \
         mock.patch("app.database.persistence.save_agent_run"), \
         mock.patch("app.database.persistence.save_graph_checkpoint"), \
         mock.patch("app.database.persistence.save_run_event"):

        res_crit = await compiled_graph.ainvoke(state_crit)
        assert res_crit["replan_needed"] is True
        assert res_crit["status"] == "WAITING_FOR_APPROVAL"


@pytest.mark.anyio
async def test_scenario_engineer_leave_replan():
    """Verify ENGINEER_ON_LEAVE triggers replanning."""
    from app.agent.graph import compiled_graph
    from optiflow_shared.tool_contracts import StructuredGoal, TimeHorizon
    import unittest.mock as mock

    state = {
        "run_id": "RUN-LEAVE",
        "simulation_mode": "Timeline",
        "status": "RECEIVED",
        "goal_text": "Optimize",
        "baseline_enterprise_snapshot": {"incidents": [], "specialists": []},
        "latest_event": {"event_type": "SPECIALIST_UNAVAILABLE", "specialist_id": "SPEC-1"}
    }

    mock_goal = StructuredGoal(
        summary="SLA Run", objectives=["SLA_PROTECTION"],
        time_horizon=TimeHorizon(value=7, unit="DAYS"),
        hard_constraints=[], soft_preferences=[], requested_actions=[], ambiguities=[], unsupported_requests=[],
        interpretation_notes=[]
    )

    with mock.patch("app.agent.nodes.interpret_goal.interpret_goal_text", return_value=mock_goal), \
         mock.patch("app.database.persistence.save_agent_run"), \
         mock.patch("app.database.persistence.save_graph_checkpoint"), \
         mock.patch("app.database.persistence.save_run_event"):

        res = await compiled_graph.ainvoke(state)
        assert res["replan_needed"] is True
        assert res["status"] == "WAITING_FOR_APPROVAL"
        assert res.get("candidate_plans") is not None


@pytest.mark.anyio
async def test_scenario_change_sla_replan():
    """Verify PRIORITY_ESCALATED triggers replanning."""
    from app.agent.graph import compiled_graph
    from optiflow_shared.tool_contracts import StructuredGoal, TimeHorizon
    import unittest.mock as mock

    state = {
        "run_id": "RUN-SLA-CHANGE",
        "simulation_mode": "Timeline",
        "status": "RECEIVED",
        "goal_text": "Optimize",
        "baseline_enterprise_snapshot": {"incidents": [], "specialists": []},
        "latest_event": {"event_type": "PRIORITY_ESCALATED"}
    }

    mock_goal = StructuredGoal(
        summary="SLA Run", objectives=["SLA_PROTECTION"],
        time_horizon=TimeHorizon(value=7, unit="DAYS"),
        hard_constraints=[], soft_preferences=[], requested_actions=[], ambiguities=[], unsupported_requests=[],
        interpretation_notes=[]
    )

    with mock.patch("app.agent.nodes.interpret_goal.interpret_goal_text", return_value=mock_goal), \
         mock.patch("app.database.persistence.save_agent_run"), \
         mock.patch("app.database.persistence.save_graph_checkpoint"), \
         mock.patch("app.database.persistence.save_run_event"):

        res = await compiled_graph.ainvoke(state)
        assert res["replan_needed"] is True
        assert res["status"] == "WAITING_FOR_APPROVAL"


@pytest.mark.anyio
async def test_scenario_resolve_ticket_no_replan():
    """Verify METRIC_UPDATED (e.g. resolve updates / commenting) does not trigger replanning."""
    from app.agent.graph import compiled_graph
    from optiflow_shared.tool_contracts import StructuredGoal, TimeHorizon
    import unittest.mock as mock

    state = {
        "run_id": "RUN-RESOLVE",
        "simulation_mode": "Timeline",
        "status": "RECEIVED",
        "goal_text": "Optimize",
        "baseline_enterprise_snapshot": {"incidents": [], "specialists": []},
        "latest_event": {"event_type": "METRIC_UPDATED"}
    }

    mock_goal = StructuredGoal(
        summary="SLA Run", objectives=["SLA_PROTECTION"],
        time_horizon=TimeHorizon(value=7, unit="DAYS"),
        hard_constraints=[], soft_preferences=[], requested_actions=[], ambiguities=[], unsupported_requests=[],
        interpretation_notes=[]
    )

    with mock.patch("app.agent.nodes.interpret_goal.interpret_goal_text", return_value=mock_goal), \
         mock.patch("app.database.persistence.save_agent_run"), \
         mock.patch("app.database.persistence.save_graph_checkpoint"), \
         mock.patch("app.database.persistence.save_run_event"):

        res = await compiled_graph.ainvoke(state)
        assert res["replan_needed"] is False
        assert res["status"] == "COMPLETED"


@pytest.mark.anyio
async def test_scenario_multiple_consecutive_events():
    """Verify consecutive events build timeline step snapshots immutably."""
    from app.agent.graph import compiled_graph
    from optiflow_shared.tool_contracts import StructuredGoal, TimeHorizon
    import unittest.mock as mock
    import copy

    mock_goal = StructuredGoal(
        summary="SLA Run", objectives=["SLA_PROTECTION"],
        time_horizon=TimeHorizon(value=7, unit="DAYS"),
        hard_constraints=[], soft_preferences=[], requested_actions=[], ambiguities=[], unsupported_requests=[],
        interpretation_notes=[]
    )

    # Helper to strip private Pregel metadata keys from the state dictionary
    def clean_state(s: dict) -> dict:
        from app.agent.state import AgentState
        return {k: v for k, v in s.items() if k in AgentState.__annotations__}

    # --- Step 1: Initial Planning run ---
    state_step1 = {
        "run_id": "RUN-CONSECUTIVE",
        "simulation_mode": "Timeline",
        "replan_needed": True,
        "status": "RECEIVED",
        "goal_text": "Optimize SLA commitments"
    }

    with mock.patch("app.agent.nodes.interpret_goal.interpret_goal_text", return_value=mock_goal), \
         mock.patch("app.database.persistence.save_agent_run"), \
         mock.patch("app.database.persistence.save_graph_checkpoint"), \
         mock.patch("app.database.persistence.save_run_event"):

        res_step1 = await compiled_graph.ainvoke(state_step1)
        assert res_step1["status"] == "WAITING_FOR_APPROVAL"
        assert len(res_step1.get("decision_history", [])) == 1

    # Simulate human approval & complete execution node to set the baseline snapshots
    # (Since complete_run sets the baseline enterprise snapshots)
    state_step2_approval = copy.deepcopy(res_step1)
    state_step2_approval["approval_status"] = "APPROVED"
    state_step2_approval["status"] = "EXECUTED"
    
    from app.agent.nodes.complete_run import complete_run
    with mock.patch("app.database.persistence.save_agent_run"), \
         mock.patch("app.database.persistence.save_graph_checkpoint"), \
         mock.patch("app.database.persistence.save_run_event"):
        res_step2_comp = await complete_run(state_step2_approval)
        assert res_step2_comp.get("baseline_enterprise_snapshot") is not None
        # Merge complete_run outputs
        state_step2_approval.update(res_step2_comp)

    # --- Step 2: Non-critical Event Ingestion (COMMENT_ADDED) ---
    state_step2_approval["latest_event"] = {"event_type": "COMMENT_ADDED"}
    state_step2_approval["status"] = "RECEIVED"

    # Make deep copy of history before step to verify immutability
    history_before_step2 = copy.deepcopy(state_step2_approval.get("decision_history", []))

    with mock.patch("app.agent.nodes.interpret_goal.interpret_goal_text", return_value=mock_goal), \
         mock.patch("app.database.persistence.save_agent_run"), \
         mock.patch("app.database.persistence.save_graph_checkpoint"), \
         mock.patch("app.database.persistence.save_run_event"):

        res_step2 = await compiled_graph.ainvoke(clean_state(state_step2_approval))
        # Should take shortcut pathway directly to complete_run
        assert res_step2["status"] == "COMPLETED"
        assert res_step2["replan_needed"] is False
        # History size should remain unchanged at 1
        assert len(res_step2.get("decision_history", [])) == 1
        assert res_step2["decision_history"] == history_before_step2

    # --- Step 3: Critical Event Ingestion (NEW_TICKET Critical) ---
    state_step3 = copy.deepcopy(res_step2)
    state_step3["latest_event"] = {"event_type": "NEW_TICKET", "priority": "CRITICAL"}
    state_step3["status"] = "RECEIVED"
    state_step3["approval_status"] = "PENDING"

    history_before_step3 = copy.deepcopy(state_step3.get("decision_history", []))

    with mock.patch("app.agent.nodes.interpret_goal.interpret_goal_text", return_value=mock_goal), \
         mock.patch("app.database.persistence.save_agent_run"), \
         mock.patch("app.database.persistence.save_graph_checkpoint"), \
         mock.patch("app.database.persistence.save_run_event"):

        res_step3 = await compiled_graph.ainvoke(clean_state(state_step3))
        # Should trigger full planning and pause
        assert res_step3["status"] == "WAITING_FOR_APPROVAL"
        assert res_step3["replan_needed"] is True
        # History size must increment to 2
        assert len(res_step3.get("decision_history", [])) == 2
        # Verify first entry remains identical (immutability check)
        assert res_step3["decision_history"][0] == history_before_step3[0]


@pytest.mark.anyio
async def test_end_to_end_demo_journey_rehearsal():
    """End-to-End Walkthrough & Demo Rehearsal representing the NeuroX Grand Finale user journey.
    
    Validates: Environment Reset -> Load Dataset -> Goal Ingest -> Interpretation ->
    Tool Calls (Fallback) -> Quality check -> Optimization -> DI presentation ->
    Halt for approval -> Human Approval -> Non-critical shortcut -> Critical event replanning ->
    Recommendation updates -> History immutability check.
    """
    from app.agent.graph import compiled_graph
    from optiflow_shared.tool_contracts import StructuredGoal, TimeHorizon
    import unittest.mock as mock
    import copy

    # Helper to strip private Pregel metadata keys from the state dictionary
    def clean_state(s: dict) -> dict:
        from app.agent.state import AgentState
        return {k: v for k, v in s.items() if k in AgentState.__annotations__}

    # 1. Reset Environment & Initialize Goal Ingestion
    goal_text = "Protect strategic accounts and minimize SLA breaches under timeline simulation."
    initial_state = {
        "run_id": "RUN-GRAND-FINALE",
        "simulation_mode": "Timeline",
        "replan_needed": True,
        "status": "RECEIVED",
        "goal_text": goal_text
    }

    mock_goal = StructuredGoal(
        summary="SLA & Strategic Protection Goal",
        objectives=["SLA_PROTECTION", "RENEWAL_PROTECTION"],
        time_horizon=TimeHorizon(value=7, unit="DAYS"),
        hard_constraints=[], soft_preferences=[], requested_actions=[], ambiguities=[], unsupported_requests=[],
        interpretation_notes=["NeuroX Mock Interpretation"]
    )

    # 2. Execute Step 1: Ingestion to Approval Halt Gate
    with mock.patch("app.agent.nodes.interpret_goal.interpret_goal_text", return_value=mock_goal), \
         mock.patch("app.database.persistence.save_agent_run"), \
         mock.patch("app.database.persistence.save_graph_checkpoint"), \
         mock.patch("app.database.persistence.save_run_event"):

        res_step1 = await compiled_graph.ainvoke(initial_state)

        # Verify initial execution completes up to waiting status
        assert res_step1["status"] == "WAITING_FOR_APPROVAL"
        assert res_step1["replan_needed"] is True
        assert len(res_step1.get("candidate_plans", [])) > 0
        assert res_step1.get("recommended_plan") is not None
        assert res_step1.get("decision_explanation") is not None
        assert len(res_step1.get("decision_history", [])) == 1

        # Check presentation layers exist
        assert res_step1.get("business_summary") is not None
        assert res_step1.get("change_summary") is not None

    # 3. Simulate Human Approval & Complete Execution (to baseline the snapshot)
    state_step2_approval = copy.deepcopy(res_step1)
    state_step2_approval["approval_status"] = "APPROVED"
    state_step2_approval["status"] = "EXECUTED"

    from app.agent.nodes.complete_run import complete_run
    with mock.patch("app.database.persistence.save_agent_run"), \
         mock.patch("app.database.persistence.save_graph_checkpoint"), \
         mock.patch("app.database.persistence.save_run_event"):
        res_step2_comp = await complete_run(state_step2_approval)
        assert res_step2_comp.get("baseline_enterprise_snapshot") is not None
        state_step2_approval.update(res_step2_comp)

    # 4. Ingest Timeline Event 1: Insignificant Change (COMMENT_ADDED) -> Bypasses replanning
    state_step2_approval["latest_event"] = {"event_type": "COMMENT_ADDED"}
    state_step2_approval["status"] = "RECEIVED"

    history_before_step2 = copy.deepcopy(state_step2_approval.get("decision_history", []))

    with mock.patch("app.agent.nodes.interpret_goal.interpret_goal_text", return_value=mock_goal), \
         mock.patch("app.database.persistence.save_agent_run"), \
         mock.patch("app.database.persistence.save_graph_checkpoint"), \
         mock.patch("app.database.persistence.save_run_event"):

        res_step2 = await compiled_graph.ainvoke(clean_state(state_step2_approval))
        # Bypasses planning, optimization and approval gate
        assert res_step2["status"] == "COMPLETED"
        assert res_step2["replan_needed"] is False
        # Recommendations & history are preserved read-only
        assert res_step2["recommended_plan"] == res_step1["recommended_plan"]
        assert len(res_step2["decision_history"]) == 1
        assert res_step2["decision_history"] == history_before_step2

    # 5. Ingest Timeline Event 2: Critical Change (NEW_TICKET Critical) -> Triggers Replan
    state_step3 = copy.deepcopy(res_step2)
    state_step3["latest_event"] = {"event_type": "NEW_TICKET", "priority": "CRITICAL"}
    state_step3["status"] = "RECEIVED"
    state_step3["approval_status"] = "PENDING"  # Reset approval status

    history_before_step3 = copy.deepcopy(state_step3.get("decision_history", []))

    with mock.patch("app.agent.nodes.interpret_goal.interpret_goal_text", return_value=mock_goal), \
         mock.patch("app.database.persistence.save_agent_run"), \
         mock.patch("app.database.persistence.save_graph_checkpoint"), \
         mock.patch("app.database.persistence.save_run_event"):

        res_step3 = await compiled_graph.ainvoke(clean_state(state_step3))

        # Re-plans and halts at the human gate again
        assert res_step3["status"] == "WAITING_FOR_APPROVAL"
        assert res_step3["replan_needed"] is True
        # Decision history appends new snapshot (size increments to 2)
        assert len(res_step3.get("decision_history", [])) == 2
        # Verify history immutability check
        assert res_step3["decision_history"][0] == history_before_step3[0]








