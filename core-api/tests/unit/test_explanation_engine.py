import pytest
from app.services.manager_preference_service import PreferenceMemory, RecommendationStats
from app.services.recommendation_engine import RecommendationResult
from app.services.explanation_engine import ExplanationEngine, ConfidenceLevel, LearningState, PersonalizedRecommendation

def test_determine_learning_state():
    """Verifies transition thresholds for learning states (cold_start < 5, learning < 20, mature >= 20)."""
    assert ExplanationEngine.determine_learning_state(0) == LearningState.COLD_START
    assert ExplanationEngine.determine_learning_state(4) == LearningState.COLD_START
    assert ExplanationEngine.determine_learning_state(5) == LearningState.LEARNING
    assert ExplanationEngine.determine_learning_state(19) == LearningState.LEARNING
    assert ExplanationEngine.determine_learning_state(20) == LearningState.MATURE
    assert ExplanationEngine.determine_learning_state(100) == LearningState.MATURE

def test_determine_confidence_level():
    """Verifies confidence mapping: COLD_START always LOW; otherwise threshold-based."""
    # 1. Cold start check
    assert ExplanationEngine.determine_confidence_level(0.9, LearningState.COLD_START) == ConfidenceLevel.LOW
    
    # 2. Thresholds
    assert ExplanationEngine.determine_confidence_level(0.2, LearningState.LEARNING) == ConfidenceLevel.LOW
    assert ExplanationEngine.determine_confidence_level(0.39, LearningState.LEARNING) == ConfidenceLevel.LOW
    assert ExplanationEngine.determine_confidence_level(0.4, LearningState.LEARNING) == ConfidenceLevel.MEDIUM
    assert ExplanationEngine.determine_confidence_level(0.69, LearningState.LEARNING) == ConfidenceLevel.MEDIUM
    assert ExplanationEngine.determine_confidence_level(0.7, LearningState.LEARNING) == ConfidenceLevel.HIGH
    assert ExplanationEngine.determine_confidence_level(0.95, LearningState.MATURE) == ConfidenceLevel.HIGH

def test_generate_explanation_reason():
    """Verifies the deterministic explanation template logic under various scenarios."""
    result = RecommendationResult(
        candidate_plan_id="P-SLA",
        candidate_index=1,
        preference_score=80.0,
        confidence=0.75
    )
    
    # 1. Cold Start case
    reason_cs = ExplanationEngine.generate_explanation_reason(
        result=result,
        memory=PreferenceMemory(total_runs=2),
        profile_name="SLA First",
        learning_state=LearningState.COLD_START
    )
    assert reason_cs == "Learning your preferences (cold-start period)..."
    
    # 2. Low Recommendation Acceptance rate case
    memory_low_acc = PreferenceMemory(
        total_runs=10,
        profile_counts={"SLA_FIRST": 5},
        recommendation_statistics=RecommendationStats(shown=4, accepted=1, rejected=3)  # 25% accept < 50%
    )
    reason_low = ExplanationEngine.generate_explanation_reason(
        result=result,
        memory=memory_low_acc,
        profile_name="SLA First",
        learning_state=LearningState.LEARNING
    )
    assert reason_low == "Recommendation confidence is limited because historical acceptance is low."
    
    # 3. Strong Historical preference count template matching
    memory_strong = PreferenceMemory(
        total_runs=15,
        profile_counts={"SLA_FIRST": 11},
        recommendation_statistics=RecommendationStats(shown=5, accepted=4, rejected=1)
    )
    reason_strong = ExplanationEngine.generate_explanation_reason(
        result=result,
        memory=memory_strong,
        profile_name="SLA First",
        learning_state=LearningState.LEARNING
    )
    assert reason_strong == "You selected SLA First in 11 of the last 15 approvals."

def test_full_integration_explain_recommendation():
    """Verifies full mapping from RecommendationResult to explained PersonalizedRecommendation."""
    result = RecommendationResult(
        candidate_plan_id="PLAN-SLA",
        candidate_index=0,
        preference_score=90.0,
        confidence=0.85
    )
    memory = PreferenceMemory(
        total_runs=22,
        profile_counts={"SLA_FIRST": 14},
        recommendation_statistics=RecommendationStats(shown=8, accepted=7, rejected=1)
    )
    candidate_plans = [
        {"plan_id": "PLAN-SLA", "profile": "SLA First"},
        {"plan_id": "PLAN-BAL", "profile": "Balanced"}
    ]
    
    rec = ExplanationEngine.explain_recommendation(
        result=result,
        memory=memory,
        candidate_plans=candidate_plans
    )
    
    assert isinstance(rec, PersonalizedRecommendation)
    assert rec.candidate_plan_id == "PLAN-SLA"
    assert rec.candidate_index == 0
    assert rec.preference_score == 90.0
    assert rec.confidence == 0.85
    assert rec.confidence_level == ConfidenceLevel.HIGH
    assert rec.learning_state == LearningState.MATURE
    assert rec.reason == "You selected SLA First in 14 of the last 22 approvals."
