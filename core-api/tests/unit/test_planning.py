import pytest
from app.goals.interpreter import interpret_goal_text
from app.goals.validator import validate_goal
from app.evidence.planner import build_evidence_requirements
from app.agent.graph import compiled_graph

@pytest.mark.asyncio
async def test_example_1_renewals_and_sla():
    # Input: Protect renewals and SLA commitments
    goal_text = "Protect renewals and SLA commitments"
    
    # 1. Interpret
    goal = interpret_goal_text(goal_text)
    assert "SLA_PROTECTION" in goal.objectives
    assert "RENEWAL_PROTECTION" in goal.objectives
    assert "COMMERCIAL_PROTECTION" in goal.objectives
    
    # 2. Validate
    val_res = validate_goal(goal)
    assert val_res.valid is True
    assert val_res.clarification_required is False
    
    # 3. Evidence Planner
    reqs = build_evidence_requirements(goal)
    req_types = {r.evidence_type for r in reqs}
    
    # SLA needs: ACTIVE_ESCALATIONS, SLA_DEADLINES, etc.
    # RENEWALS needs: RENEWAL_DATE, CUSTOMER_ARR, etc.
    assert "ACTIVE_ESCALATIONS" in req_types
    assert "RENEWAL_DATE" in req_types
    assert "CUSTOMER_ARR" in req_types
    
    # Run in compiled graph to check tool selection
    state = {
        "run_id": "RUN-1",
        "goal_text": goal_text,
        "status": "RECEIVED"
    }
    final_state = await compiled_graph.ainvoke(state)
    assert final_state["status"] == "COMPLETED"
    
    selected = {t["toolName"]: t for t in final_state["selected_tools"]}
    assert selected["crm-service"]["selected"] is True
    assert selected["incident-service"]["selected"] is True
    assert selected["workforce-service"]["selected"] is True
    assert selected["communication-service"]["selected"] is False

@pytest.mark.asyncio
async def test_example_2_workload_fairly():
    # Input: Balance workload fairly
    goal_text = "Balance workload fairly"
    
    # 1. Interpret
    goal = interpret_goal_text(goal_text)
    assert "CUSTOMER_FAIRNESS" in goal.objectives
    assert "WORKLOAD_PROTECTION" in goal.objectives
    
    # 2. Validate
    val_res = validate_goal(goal)
    assert val_res.valid is True
    
    # 3. Evidence Planner
    reqs = build_evidence_requirements(goal)
    req_types = {r.evidence_type for r in reqs}
    assert "CURRENT_WORKLOAD" in req_types
    assert "WAITING_TIME" in req_types
    
    # Run in graph
    state = {
        "run_id": "RUN-2",
        "goal_text": goal_text,
        "status": "RECEIVED"
    }
    final_state = await compiled_graph.ainvoke(state)
    selected = {t["toolName"]: t for t in final_state["selected_tools"]}
    
    # Workforce must be selected
    assert selected["workforce-service"]["selected"] is True
    # CRM not selected
    assert selected["crm-service"]["selected"] is False

@pytest.mark.asyncio
async def test_example_3_empty_goal():
    # Input: empty string
    goal_text = "   "
    goal = interpret_goal_text(goal_text)
    val_res = validate_goal(goal)
    
    # Must fail validation
    assert val_res.valid is False
    assert "Goal summary cannot be empty." in val_res.blocking_reasons

@pytest.mark.asyncio
async def test_example_4_duplicate_objectives():
    # Input: SLA commitments and SLA commitments
    goal_text = "Protect SLA commitments and SLA commitments"
    goal = interpret_goal_text(goal_text)
    
    # objectives list has deduplicated
    assert len(goal.objectives) == 1
    assert goal.objectives == ["SLA_PROTECTION"]
    
    # Evidence list is deduplicated
    reqs = build_evidence_requirements(goal)
    req_types = [r.evidence_type for r in reqs]
    assert len(req_types) == len(set(req_types))
