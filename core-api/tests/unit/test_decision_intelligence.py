import pytest
import time
import unittest.mock as mock
from app.services.decision_intelligence import DecisionIntelligenceService, DecisionExplanation
from app.services.decision_presentation import DecisionPresentationService
from app.agent.nodes.decision_intelligence import decision_intelligence

def test_decision_explanation_skeleton_compiles():
    """Verify that the DTO structure is valid and serializes correctly."""
    mock_state = {
        "run_id": "RUN-TEST-123",
        "scenario_id": "scen-1",
        "timeline_position": 2,
        "latest_event": {
            "event_type": "NEW_TICKET",
            "priority": "HIGH",
            "incident_id": "INC-001"
        }
    }
    
    explanation = DecisionIntelligenceService.build_explanation(mock_state)
    assert isinstance(explanation, DecisionExplanation)
    assert explanation.metadata.run_id == "RUN-TEST-123"
    assert explanation.metadata.timeline_position == 2
    assert explanation.metadata.trigger_event is not None
    assert explanation.metadata.trigger_event.event_type == "NEW_TICKET"
    assert explanation.metadata.trigger_event.priority == "HIGH"
    
    assert "Recommended" in explanation.recommendation.selection_reason or explanation.recommendation.selection_reason == "Initial skeleton baseline profile selected."
    assert explanation.outcome.status == "Pending"
    
    # Check JSON serialization compatibility
    serialized = explanation.model_dump(mode="json")
    assert serialized["metadata"]["decision_id"].startswith("DEC-")
    assert serialized["executive_summary"]["headline"] == "Strategy Recommendation: Balanced"


@pytest.mark.anyio
async def test_decision_intelligence_node_execution():
    """Verify that the decision_intelligence node executes successfully and enriches state."""
    mock_state = {
        "run_id": "RUN-TEST-NODE",
        "scenario_id": "scen-2",
        "timeline_position": 1,
        "latest_event": {
            "event_type": "NEW_TICKET",
            "priority": "HIGH",
            "incident_id": "INC-001"
        },
        "enterprise_state": {
            "customers": [{"customer_id": "CUS-A", "arr": 250000.0}],
            "escalations": [{"incident_id": "INC-001", "title": "API timeout", "priority": "HIGH"}],
            "specialists": [{"specialist_id": "SPEC-1", "name": "Alice"}]
        },
        "recommended_plan": {
            "profile": "SLA-First",
            "explanation": "- Focus on SLA-critical items.\n- Protect strategic accounts.",
            "allocations": [{"incident_id": "INC-001", "specialist_id": "SPEC-1"}]
        },
        "candidate_plans": [
            {
                "plan_id": "plan-1",
                "profile": "SLA-First",
                "objective_value": 90.0,
                "metrics": {"sla_score": 95.0, "match_rate": 95.0, "arr_protected": 250000.0}
            },
            {
                "plan_id": "plan-2",
                "profile": "Balanced",
                "objective_value": 75.0,
                "metrics": {"sla_score": 80.0, "match_rate": 80.0, "arr_protected": 200000.0}
            }
        ]
    }
    
    # Run the node first time
    res = await decision_intelligence(mock_state)
    assert "decision_explanation" in res
    assert res["business_summary"] is not None
    assert res["change_summary"] is not None
    assert len(res["decision_history"]) == 1
    
    # Check concise summary formats
    assert "Strategy Recommendation: SLA-First" in res["business_summary"]
    
    # Check audit scorecard table contains alternative candidates
    assert "Recommended Profile Strategy: SLA-First" in res["change_summary"]
    assert "| #2 | Balanced |" in res["change_summary"]
    assert "Assign specialist Alice" in res["change_summary"]
    
    # Run the node second time to verify immutable history appending
    mock_state["decision_history"] = res["decision_history"]
    res_second = await decision_intelligence(mock_state)
    assert len(res_second["decision_history"]) == 2


@pytest.mark.anyio
async def test_decision_intelligence_node_exception_safeguard():
    """Verify that node catches exceptions from the service and returns empty state updates."""
    mock_state = {
        "run_id": "RUN-FAIL",
    }
    
    # Mock service build_explanation to raise an exception
    with mock.patch("app.services.decision_intelligence.DecisionIntelligenceService.build_explanation", side_effect=ValueError("Service error")):
        res = await decision_intelligence(mock_state)
        # Verify it did not raise and returned a safe fallback dict (passive layer safety)
        assert res == {"decision_explanation": None}


def test_decision_intelligence_edge_cases_empty_state():
    """Verify that the DTO service degrades gracefully when input state is empty or missing keys."""
    empty_state = {"run_id": "RUN-EMPTY"}
    
    # Service builder must not throw exceptions
    explanation = DecisionIntelligenceService.build_explanation(empty_state)
    assert isinstance(explanation, DecisionExplanation)
    assert explanation.metadata.run_id == "RUN-EMPTY"
    assert explanation.metadata.scenario_id is None
    assert explanation.metadata.trigger_event is None
    
    assert explanation.recommendation.selected_profile == "Balanced"
    assert not explanation.recommendation.alternatives
    assert not explanation.actions
    assert not explanation.business_impact.kpis


def test_decision_presentation_edge_cases_empty_dto():
    """Verify that formatting is clean even for empty fields."""
    empty_state = {"run_id": "RUN-EMPTY"}
    explanation = DecisionIntelligenceService.build_explanation(empty_state)
    
    # Presentation formatter must not throw exceptions on empty schemas
    presentation = DecisionPresentationService.generate_presentation(explanation)
    assert presentation.business_summary is not None
    assert presentation.change_summary is not None
    assert presentation.markdown_report is not None
    
    # Check fallback strings in output summaries
    assert "*No alternative candidate strategies recorded.*" in presentation.change_summary
    assert "Strategy Recommendation: Balanced" in presentation.business_summary
    assert "Minimizes context-switching fatigue" in presentation.change_summary


def test_decision_intelligence_micro_benchmark():
    """Verify that the in-memory decision layer introduces negligible latency (under 5ms average)."""
    mock_state = {
        "run_id": "RUN-BENCH",
        "scenario_id": "scen-bench",
        "timeline_position": 4,
        "latest_event": {"event_type": "NEW_TICKET", "priority": "HIGH"},
        "enterprise_state": {
            "customers": [{"customer_id": "C", "arr": 150000.0}],
            "escalations": [{"incident_id": "I", "title": "T", "priority": "HIGH"}],
            "specialists": [{"specialist_id": "S", "name": "N"}]
        },
        "recommended_plan": {"profile": "Balanced", "allocations": [{"incident_id": "I", "specialist_id": "S"}]},
        "candidate_plans": [{"plan_id": "p1", "profile": "Balanced", "objective_value": 80.0, "metrics": {"match_rate": 80.0}}]
    }
    
    warmup_count = 10
    bench_count = 100
    
    # Warmup
    for _ in range(warmup_count):
        exp = DecisionIntelligenceService.build_explanation(mock_state)
        DecisionPresentationService.generate_presentation(exp)
        
    start_time = time.perf_counter()
    for _ in range(bench_count):
        exp = DecisionIntelligenceService.build_explanation(mock_state)
        DecisionPresentationService.generate_presentation(exp)
    end_time = time.perf_counter()
    
    total_duration_ms = (end_time - start_time) * 1000.0
    avg_latency_ms = total_duration_ms / bench_count
    
    print(f"\n[BENCHMARK] Total duration for {bench_count} runs: {total_duration_ms:.2f}ms")
    print(f"[BENCHMARK] Average latency per run: {avg_latency_ms:.4f}ms")
    
    # Assert latency is under 5.0 milliseconds
    assert avg_latency_ms < 5.0, f"Average latency ({avg_latency_ms:.2f}ms) exceeded 5.0ms threshold!"
