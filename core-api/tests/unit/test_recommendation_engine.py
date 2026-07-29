import pytest
from app.services.manager_preference_service import PreferenceMemory, RecommendationStats
from app.services.recommendation_engine import RecommendationEngine, RecommendationResult
from app.agent.nodes.generate_personalized_plan import generate_personalized_plan
from app.database.session import async_session
from app.database.models import ManagerPreference
from app.database.persistence import save_manager_preference
from sqlalchemy import delete

def test_recommendation_result_model():
    """Verifies fields of the RecommendationResult model validate correctly."""
    res = RecommendationResult(
        candidate_plan_id="PLAN-123",
        candidate_index=2,
        preference_score=85.5,
        confidence=0.75
    )
    assert res.candidate_plan_id == "PLAN-123"
    assert res.candidate_index == 2
    assert res.preference_score == 85.5
    assert res.confidence == 0.75

def test_cold_start():
    """Verifies that under cold start (total_runs < 5), it mirrors the highest objective solver plan with 0.0 confidence."""
    candidates = [
        {"plan_id": "PLAN-BALANCED", "profile": "Balanced", "objective_value": 40.0},
        {"plan_id": "PLAN-SLA-FIRST", "profile": "SLA First", "objective_value": 60.0},
    ]
    # total_runs = 3 (under 5)
    memory = PreferenceMemory(total_runs=3, profile_counts={"BALANCED": 3})
    
    result = RecommendationEngine.rank_candidates(candidates, memory, goal_text="Goal")
    assert result.candidate_plan_id == "PLAN-SLA-FIRST"  # Highest objective
    assert result.candidate_index == 1
    assert result.confidence == 0.0
    assert result.preference_score == 0.0

def test_learned_preferences_change_ranking():
    """Verifies that learned preferences can rank a plan higher than a slightly higher objective solver plan."""
    candidates = [
        {"plan_id": "PLAN-BALANCED", "profile": "Balanced", "objective_value": 85.0},
        {"plan_id": "PLAN-SLA-FIRST", "profile": "SLA First", "objective_value": 80.0},
    ]
    # total_runs = 10, SLA First has been chosen 9 times (90%)
    memory = PreferenceMemory(
        total_runs=10,
        profile_counts={"SLA_FIRST": 9},
        recommendation_statistics=RecommendationStats(shown=5, accepted=4, rejected=1)
    )
    
    # Balanced rank: 85.0 + 0.0 preference score = 85.0
    # SLA First rank: 80.0 + (0.9 * 0.7) * 100 = 80.0 + 63.0 = 143.0
    result = RecommendationEngine.rank_candidates(candidates, memory, goal_text="Default goal")
    assert result.candidate_plan_id == "PLAN-SLA-FIRST"
    assert result.candidate_index == 1
    assert result.preference_score > 0.0
    assert result.confidence > 0.0

def test_confidence_calculation():
    """Verifies that confidence calculation correctly weights profile consistency and recommendation acceptance."""
    # 1. Zero runs -> 0.0
    memory_empty = PreferenceMemory()
    assert RecommendationEngine.calculate_confidence(memory_empty) == 0.0
    
    # 2. Dominated runs + accepted recs -> High confidence
    memory_high = PreferenceMemory(
        total_runs=10,
        profile_counts={"SLA_FIRST": 9},
        recommendation_statistics=RecommendationStats(shown=5, accepted=5, rejected=0)
    )
    # Dominance: 9/10 = 0.9. Acceptance: 5/5 = 1.0. Confidence = 0.9 * 0.6 + 1.0 * 0.4 = 0.54 + 0.4 = 0.94
    confidence = RecommendationEngine.calculate_confidence(memory_high)
    assert round(confidence, 2) == 0.94

@pytest.mark.asyncio
async def test_personalized_node_integration():
    """Verifies that the LangGraph node loads preferences and returns a recommendation reference."""
    state = {
        "run_id": "RUN-REC-NODE-TEST",
        "goal_text": "Optimize renewals",
        "candidate_plans": [
            {"plan_id": "PLAN-BALANCED", "profile": "Balanced", "objective_value": 70.0},
            {"plan_id": "PLAN-REVENUE-FIRST", "profile": "Revenue First", "objective_value": 65.0},
        ]
    }
    
    # Write a detailed preference history to database: 10 runs, Revenue First chosen 9 times
    async with async_session() as session:
        async with session.begin():
            await session.execute(delete(ManagerPreference))
            
            history = {
                "version": 1,
                "total_runs": 10,
                "profile_counts": {"REVENUE_FIRST": 9},
                "recommendation_statistics": {
                    "shown": 5,
                    "accepted": 4,
                    "rejected": 1
                },
                "learned_constraints": ["Protect renewals"],
                "updated_at": "2026-07-29T20:51:27Z"
            }
            await save_manager_preference(session, history)
            
    # Run the node
    node_update = await generate_personalized_plan(state)
    assert "personalized_recommendation" in node_update
    
    rec = node_update["personalized_recommendation"]
    assert rec is not None
    assert rec["candidate_plan_id"] == "PLAN-REVENUE-FIRST"
    assert rec["profile"] == "Revenue First"
    assert rec["preference_score"] > 0.0
    assert rec["confidence"] > 0.0
