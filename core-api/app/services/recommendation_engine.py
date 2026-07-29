import logging
from typing import Dict, List, Any, Optional
from pydantic import BaseModel
from app.config.preference_config import PreferenceConfig, OptimizationProfile
from app.services.manager_preference_service import PreferenceMemory

logger = logging.getLogger("core-api.services.recommendation_engine")

class RecommendationResult(BaseModel):
    candidate_plan_id: str
    candidate_index: int
    preference_score: float
    confidence: float

class RecommendationEngine:
    """Recommendation Engine for Manager Preferences.
    
    Responsibilities:
    - Computes mathematical preference and ranking scores for candidate plans.
    - Calculates aggregate numeric recommendation confidence.
    - Evaluates semantic goal text keyword matches.
    
    Intentionally does NOT do:
    - Load, save, or validate preferences in the database (delegated to ManagerPreferenceService).
    - Update stats or profile choice metrics (delegated to PreferenceLearningEngine).
    - Format natural language explanation reasons or determine confidence labels (delegated to ExplanationEngine).
    """
    @staticmethod
    def calculate_profile_score(profile_counts: Dict[str, int], total_runs: int, profile: str) -> float:
        """Calculates a frequency score for a profile, between 0.0 and 1.0."""
        if total_runs <= 0:
            return 0.0
        norm_profile = PreferenceConfig.normalize_profile(profile)
        count = profile_counts.get(norm_profile.value, 0)
        return float(count / total_runs)

    @staticmethod
    def calculate_acceptance_score(shown: int, accepted: int) -> float:
        """Calculates historical acceptance score of recommendations, between 0.0 and 1.0."""
        if shown <= 0:
            # Cold-start / default acceptance baseline from configuration
            return PreferenceConfig.DEFAULT_ACCEPTANCE_RATE_BASELINE
        return float(accepted / shown)

    @staticmethod
    def calculate_goal_similarity(goal_text: Optional[str], profile: str) -> float:
        """Computes similarity of current goal description keywords to the profile's characteristics."""
        if not goal_text:
            return 0.0
            
        normalized = goal_text.lower()
        norm_profile = PreferenceConfig.normalize_profile(profile)
        
        # Define keywords mapping to each profile using enums
        keywords = {
            OptimizationProfile.SLA_FIRST: ["sla", "breach", "incident", "critical", "deadline", "commitments"],
            OptimizationProfile.REVENUE_FIRST: ["arr", "revenue", "renew", "commercial", "banking", "customer", "renewals"],
            OptimizationProfile.FAIRNESS_FIRST: ["workload", "overload", "fair", "fatigue", "capacity", "daniel", "balance"],
            OptimizationProfile.BALANCED: ["balance", "compromise", "optimize", "general"]
        }
        
        target_kws = keywords.get(norm_profile, [])
        if not target_kws:
            return 0.0
            
        # Count how many target keywords occur in the goal text
        match_count = sum(1 for kw in target_kws if kw in normalized)
        return 1.0 if match_count > 0 else 0.0

    @staticmethod
    def calculate_confidence(memory: PreferenceMemory) -> float:
        """Extensible helper combining multiple factors to output recommendation confidence (0.0 to 1.0)."""
        if memory.total_runs == 0:
            return 0.0
            
        # 1. Profile Dominance factor (is one profile strongly favored?)
        max_profile_ratio = 0.0
        if memory.profile_counts:
            max_count = max(memory.profile_counts.values())
            max_profile_ratio = max_count / memory.total_runs
            
        # 2. Acceptance rate factor
        acc_rate = RecommendationEngine.calculate_acceptance_score(
            memory.recommendation_statistics.shown,
            memory.recommendation_statistics.accepted
        )
        
        # Extensible combination logic using configuration weights
        return float(
            (max_profile_ratio * PreferenceConfig.DOMINANCE_FACTOR_WEIGHT) + 
            (acc_rate * PreferenceConfig.ACCEPTANCE_FACTOR_WEIGHT)
        )

    @staticmethod
    def rank_candidates(
        candidate_plans: List[Dict[str, Any]],
        memory: PreferenceMemory,
        goal_text: Optional[str] = None
    ) -> RecommendationResult:
        """Ranks candidate plans using preferences and optimization outputs, returning the recommendation result."""
        if not candidate_plans:
            raise ValueError("Cannot rank empty candidate plans list.")
            
        # Cold start handling: if historical runs are below configured threshold
        if memory.total_runs < PreferenceConfig.COLD_START_RUNS:
            # Solver's default recommendation is the plan with highest objective value
            best_plan = max(candidate_plans, key=lambda p: p.get("objective_value", 0.0))
            best_idx = candidate_plans.index(best_plan)
            
            return RecommendationResult(
                candidate_plan_id=best_plan.get("plan_id", "unknown"),
                candidate_index=best_idx,
                preference_score=0.0,
                confidence=0.0
            )
            
        # Scoring candidates
        best_candidate = None
        best_score = -999999.0
        best_pref_score = 0.0
        best_idx = 0
        
        for idx, plan in enumerate(candidate_plans):
            profile = plan.get("profile", "BALANCED")
            norm_profile = PreferenceConfig.normalize_profile(profile)
            
            # Compute score parts
            prof_score = RecommendationEngine.calculate_profile_score(
                memory.profile_counts,
                memory.total_runs,
                norm_profile.value
            )
            sim_score = RecommendationEngine.calculate_goal_similarity(goal_text, norm_profile.value)
            
            # Combine to get final preference score using configuration weights
            preference_score = (
                prof_score * PreferenceConfig.PROFILE_WEIGHT + 
                sim_score * PreferenceConfig.GOAL_SIMILARITY_WEIGHT
            ) * PreferenceConfig.MAX_PREF_SCORE
            
            # Combine optimization score (objective_value) and preference_score for ranking
            opt_score = float(plan.get("objective_value", 0.0))
            combined_rank_score = opt_score + preference_score
            
            if combined_rank_score > best_score:
                best_score = combined_rank_score
                best_pref_score = preference_score
                best_candidate = plan
                best_idx = idx
                
        confidence = RecommendationEngine.calculate_confidence(memory)
        
        return RecommendationResult(
            candidate_plan_id=best_candidate.get("plan_id", "unknown"),
            candidate_index=best_idx,
            preference_score=round(best_pref_score, 2),
            confidence=round(confidence, 2)
        )
