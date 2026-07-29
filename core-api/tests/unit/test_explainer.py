import pytest
from unittest.mock import MagicMock, patch
from app.optimizer.explainer import (
    build_explanation_prompt,
    generate_deterministic_fallback_explanation,
    explain_plan
)
from app.llm_settings.service import (
    RuntimeCredential,
    RuntimeLLMSettings,
    RuntimeProvider,
)


def runtime_settings(configured: bool) -> RuntimeLLMSettings:
    if not configured:
        return RuntimeLLMSettings(1, "rules_only", None, {}, "rules_only")
    return RuntimeLLMSettings(
        1,
        "ai_assisted",
        "gemini",
        {
            "gemini": RuntimeProvider(
                "gemini-3.6-flash",
                (RuntimeCredential("Primary", "test-key", 0),),
            )
        },
        "database",
    )

@pytest.fixture
def sample_data():
    ent_state = {
        "specialists": [
            {"specialist_id": "SPEC-ALICE", "name": "Alice", "skills": ["integration"], "capacity": 2, "current_workload": 0}
        ],
        "escalations": [
            {"incident_id": "INC-01", "customer_id": "CUS-ALPHA", "title": "API bug", "priority": "CRITICAL", "status": "OPEN"}
        ],
        "customers": [
            {"customer_id": "CUS-ALPHA", "arr": 200000.0}
        ]
    }
    
    plan = {
        "plan_id": "PLAN-BALANCED",
        "profile": "Balanced",
        "objective_value": 90.0,
        "allocations": [
            {"incident_id": "INC-01", "specialist_id": "SPEC-ALICE", "matched_skills": ["integration"]}
        ],
        "unassigned_incidents": [],
        "metrics": {
            "match_rate": 100.0,
            "assigned_count": 1,
            "unassigned_count": 0
        }
    }
    return plan, ent_state

def test_build_explanation_prompt(sample_data):
    plan, ent_state = sample_data
    prompt = build_explanation_prompt("Balanced", plan, ent_state)
    
    assert "PLAN PROFILE: Balanced" in prompt
    assert "Assigned incident 'API bug' (INC-01) to specialist Alice (SPEC-ALICE)" in prompt
    assert "Match rate: 100.0%" in prompt

def test_generate_deterministic_fallback_explanation(sample_data):
    plan, ent_state = sample_data
    
    # 1. Balanced profile fallback
    fb_balanced = generate_deterministic_fallback_explanation("Balanced", plan, ent_state)
    assert "### Plan Justification: Balanced Profile" in fb_balanced
    assert "Allocated 1 active incidents across 1 specialists" in fb_balanced
    assert "Evenly distributes tasks" in fb_balanced
    
    # 2. SLA-First profile fallback
    fb_sla = generate_deterministic_fallback_explanation("SLA-First", plan, ent_state)
    assert "### Plan Justification: SLA-First Profile" in fb_sla
    assert "urgent SLA commitments" in fb_sla

def test_explain_plan_fallback_no_config(sample_data):
    plan, ent_state = sample_data

    explanation = explain_plan(
        "Balanced",
        plan,
        ent_state,
        runtime_settings=runtime_settings(False),
    )
    assert "### Plan Justification: Balanced Profile" in explanation

def test_explain_plan_llm_success(sample_data):
    plan, ent_state = sample_data
    
    with patch("app.optimizer.explainer.get_llm_provider") as mock_get_provider:
        mock_provider = MagicMock()
        mock_provider.generate_text.return_value = "Mocked LLM Justification"
        mock_get_provider.return_value = mock_provider
        
        explanation = explain_plan(
            "Balanced",
            plan,
            ent_state,
            runtime_settings=runtime_settings(True),
        )
        assert explanation == "Mocked LLM Justification"
        mock_provider.generate_text.assert_called_once()

def test_explain_plan_llm_error_fallback(sample_data):
    plan, ent_state = sample_data
    
    with patch("app.optimizer.explainer.get_llm_provider") as mock_get_provider:
        mock_provider = MagicMock()
        mock_provider.generate_text.side_effect = Exception("API connection timeout")
        mock_get_provider.return_value = mock_provider
        
        explanation = explain_plan(
            "Balanced",
            plan,
            ent_state,
            runtime_settings=runtime_settings(True),
        )
        # Should catch exception and gracefully return fallback
        assert "### Plan Justification: Balanced Profile" in explanation
