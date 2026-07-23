import pytest
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
    
    # 3. Execute graph asynchronously
    final_state = await compiled_graph.ainvoke(initial_state)
    
    # 4. Assert updates propagated through the nodes
    assert final_state["run_id"] == "RUN-TEST-001"
    assert final_state["goal_text"] == "Minimize SLA breaches and protect customer renewals."
    assert final_state["status"] == "COMPLETED"
    
    # Check that interpret_goal node populated structured_goal
    assert final_state["structured_goal"] is not None
    assert final_state["structured_goal"]["objectives"] == ["SLA_PROTECTION", "RENEWAL_PROTECTION"]
    
    # Check plan_evidence populated evidence_requirements
    assert len(final_state["evidence_requirements"]) == 2
    assert final_state["evidence_requirements"][0]["evidence_type"] == "ACTIVE_ESCALATIONS"
    
    # Check select_tools populated selected_tools
    assert len(final_state["selected_tools"]) == 2
    
    # Check execute_tools populated tool_results
    assert len(final_state["tool_results"]) == 2
    
    # Check build_state populated enterprise_state
    assert final_state["enterprise_state"] is not None
    assert final_state["enterprise_state"]["snapshot_id"] == "SNAP-001"
