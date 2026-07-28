import pytest
from unittest.mock import patch
from optiflow_shared.tool_contracts import StructuredGoal, TimeHorizon
from app.agent.graph import compiled_graph

@pytest.mark.asyncio
async def test_graph_compilation_and_execution():
    # 1. Assert graph is compiled
    assert compiled_graph is not None
    
    # 2. Setup initial state input
    initial_state = {
        "run_id": "RUN-TEST-001",
        "goal_text": "Minimize SLA breaches and protect customer renewals.",
        "status": "RECEIVED"
    }
    
    # Mock interpreter to prevent non-deterministic Gemini / fallback calls
    mock_goal = StructuredGoal(
        summary="Minimize SLA breaches and protect customer renewals.",
        objectives=["SLA_PROTECTION", "RENEWAL_PROTECTION"],
        time_horizon=TimeHorizon(value=7, unit="DAYS"),
        hard_constraints=[],
        soft_preferences=[],
        requested_actions=[],
        ambiguities=[],
        unsupported_requests=[],
        interpretation_notes=["Mocked for graph integration testing"]
    )
    
    with patch("app.agent.nodes.interpret_goal.interpret_goal_text", return_value=mock_goal):
        # 3. Execute graph asynchronously
        final_state = await compiled_graph.ainvoke(initial_state)
        
        # 4. Assert updates propagated through the nodes
        assert final_state["run_id"] == "RUN-TEST-001"
        assert final_state["goal_text"] == "Minimize SLA breaches and protect customer renewals."
        assert final_state["status"] == "WAITING_FOR_APPROVAL"
        
        # Check that interpret_goal node populated structured_goal
        assert final_state["structured_goal"] is not None
        assert "SLA_PROTECTION" in final_state["structured_goal"]["objectives"]
        assert "RENEWAL_PROTECTION" in final_state["structured_goal"]["objectives"]
        
        # Check plan_evidence populated evidence_requirements
        assert len(final_state["evidence_requirements"]) > 0
        
        # Check select_tools populated selected_tools (should contain all 4 microservices tags)
        assert len(final_state["selected_tools"]) == 4
        
        # Check execute_tools populated tool_results
        assert len(final_state["tool_results"]) == 3
        
        # Check build_state populated enterprise_state
        assert final_state["enterprise_state"] is not None
        assert final_state["enterprise_state"]["snapshot_id"] == "SNAP-RUN-TEST-001"
        
        # Check generate_plans populated candidate_plans and explanations
        assert "candidate_plans" in final_state
        assert len(final_state["candidate_plans"]) in (2, 4)
        for plan in final_state["candidate_plans"]:
            assert "explanation" in plan
            assert plan["explanation"] is not None
            assert len(plan["explanation"]) > 0
