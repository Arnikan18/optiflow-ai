import logging
from enum import Enum
from typing import Dict, List, Any, Optional
from pydantic import BaseModel
from app.config.preference_config import PreferenceConfig, OptimizationProfile
from app.services.manager_preference_service import PreferenceMemory
from app.services.recommendation_engine import RecommendationResult

logger = logging.getLogger("core-api.services.explanation_engine")

class ConfidenceLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"

class LearningState(str, Enum):
    COLD_START = "COLD_START"
    LEARNING = "LEARNING"
    MATURE = "MATURE"

class PersonalizedRecommendation(BaseModel):
    candidate_plan_id: str
    candidate_index: int
    preference_score: float
    confidence: float
    confidence_level: ConfidenceLevel
    learning_state: LearningState
    reason: str

class ExplanationEngine:
    """Explanation Engine for Manager Preferences.
    
    Responsibilities:
    - Converts raw numeric recommendation outputs to human-readable structured recommendations.
    - Decides learning state and confidence level enums based on configuration bounds.
    - Renders text explanation reasons using deterministic templates.
    
    Intentionally does NOT do:
    - Calculate numeric preference weights or rank candidate plans (delegated to RecommendationEngine).
    - Load, save, or serialize preference records in SQLite (delegated to ManagerPreferenceService).
    """
    @staticmethod
    def determine_learning_state(total_runs: int) -> LearningState:
        """Determines the learning state based on total run history count."""
        if total_runs < PreferenceConfig.COLD_START_RUNS:
            return LearningState.COLD_START
        elif total_runs < PreferenceConfig.MATURE_LEARNING_RUNS:
            return LearningState.LEARNING
        return LearningState.MATURE

    @staticmethod
    def determine_confidence_level(confidence: float, learning_state: LearningState) -> ConfidenceLevel:
        """Maps numeric confidence score to ConfidenceLevel enum."""
        if learning_state == LearningState.COLD_START:
            return ConfidenceLevel.LOW
            
        if confidence < PreferenceConfig.CONFIDENCE_LOW_THRESHOLD:
            return ConfidenceLevel.LOW
        elif confidence < PreferenceConfig.CONFIDENCE_HIGH_THRESHOLD:
            return ConfidenceLevel.MEDIUM
        return ConfidenceLevel.HIGH

    @staticmethod
    def generate_explanation_reason(
        result: RecommendationResult,
        memory: PreferenceMemory,
        profile_name: str,
        learning_state: LearningState
    ) -> str:
        """Generates a deterministic text explanation for the recommendation using pre-defined templates."""
        if learning_state == LearningState.COLD_START:
            return "Learning your preferences (cold-start period)..."
            
        # 1. Check if historical acceptance rate of personalized recommendations is low
        shown = memory.recommendation_statistics.shown
        accepted = memory.recommendation_statistics.accepted
        if shown >= PreferenceConfig.ACCEPTANCE_SHOWN_MIN and (accepted / shown) < PreferenceConfig.ACCEPTANCE_LOW_RATIO_THRESHOLD:
            return "Recommendation confidence is limited because historical acceptance is low."
            
        # 2. Check for strong historical preference
        norm_profile = PreferenceConfig.normalize_profile(profile_name)
        count = memory.profile_counts.get(norm_profile.value, 0)
        
        if count > 0:
            # Match user template exactly: "You selected SLA First in 14 of the last 18 approvals."
            return f"You selected {profile_name} in {count} of the last {memory.total_runs} approvals."
            
        # 3. Fallback
        return "Recommended based on current goal alignment and solver objectives."

    @staticmethod
    def explain_recommendation(
        result: RecommendationResult,
        memory: PreferenceMemory,
        candidate_plans: List[Dict[str, Any]]
    ) -> PersonalizedRecommendation:
        """Converts a numeric RecommendationResult into a fully explained PersonalizedRecommendation."""
        learning_state = ExplanationEngine.determine_learning_state(memory.total_runs)
        confidence_level = ExplanationEngine.determine_confidence_level(result.confidence, learning_state)
        
        # Get profile name of the recommended candidate
        best_plan = candidate_plans[result.candidate_index]
        profile_name = best_plan.get("profile", "Balanced")
        
        reason = ExplanationEngine.generate_explanation_reason(
            result=result,
            memory=memory,
            profile_name=profile_name,
            learning_state=learning_state
        )
        
        return PersonalizedRecommendation(
            candidate_plan_id=result.candidate_plan_id,
            candidate_index=result.candidate_index,
            preference_score=result.preference_score,
            confidence=result.confidence,
            confidence_level=confidence_level,
            learning_state=learning_state,
            reason=reason
        )
