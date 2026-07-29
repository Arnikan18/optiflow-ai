import logging
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from app.config.preference_config import PreferenceConfig, OptimizationProfile, DEFAULT_PROFILE_EXPLANATIONS

logger = logging.getLogger("core-api.services.candidate_comparison_builder")

class CandidatePlanSummary(BaseModel):
    profile: str
    objective_score: float
    sla_score: float
    revenue_score: float
    fairness_score: float
    workload_score: float
    selected: bool
    recommendation_reason: str
    rank: int

class CandidateComparisonBuilder:
    """Pure transformation helper to build candidate plan summaries for side-by-side comparison.
    
    Responsibilities:
    - Transform raw candidate plans and contextual metrics into typed CandidatePlanSummary DTOs.
    - Compute derived metrics (e.g. scaling raw ARR to a percentage revenue score).
    - Sort and assign rank based on objective scores.
    
    Intentionally does NOT do:
    - Query database records or other services.
    - Modify optimization outputs.
    """
    @staticmethod
    def build_summaries(
        plans: List[Dict[str, Any]],
        customers: List[Dict[str, Any]],
        recommended_plan_id: Optional[str] = None,
        personalized_reason: Optional[str] = None
    ) -> List[CandidatePlanSummary]:
        """Maps candidate plans and contextual data to a list of CandidatePlanSummary objects."""
        if not plans:
            return []
            
        total_arr = sum(float(c.get("arr") or 0.0) for c in customers)
            
        # 1. Sort plans by objective value descending to assign ranks.
        # Note: 'rank' reflects the mathematical optimizer's preference ordering (1-indexed),
        # whereas 'selected' is independent and reflects the final decision of the RecommendationEngine.
        sorted_plans = sorted(plans, key=lambda p: p.get("objective_value", 0.0), reverse=True)
        
        summaries = []
        for index, plan in enumerate(sorted_plans):
            plan_id = plan.get("plan_id")
            profile_name = plan.get("profile", "Balanced")
            norm_profile = PreferenceConfig.normalize_profile(profile_name)
            
            # Determine selection status (RecommendationEngine preference)
            selected = (plan_id == recommended_plan_id) if recommended_plan_id else False
            
            # Retrieve explanation reason (preference reason if recommended/selected, else default profile-based text)
            reason = ""
            if selected and personalized_reason:
                reason = personalized_reason
            else:
                reason = DEFAULT_PROFILE_EXPLANATIONS.get(norm_profile, "Custom optimization profile")
                
            metrics = plan.get("metrics", {})
            
            # Resolve metrics
            objective_score = float(plan.get("objective_value", 0.0))
            sla_score = float(metrics.get("sla_score", metrics.get("match_rate", 0.0)))
            fairness_score = float(metrics.get("fairness_score", metrics.get("match_rate", 0.0)))
            workload_score = float(metrics.get("context_switching_score", metrics.get("match_rate", 0.0)))
            
            # Calculate revenue score out of 100 based on arr_protected / total_arr
            if "arr_protected" in metrics:
                arr_protected = float(metrics.get("arr_protected", 0.0))
                revenue_score = float((arr_protected / total_arr * 100.0) if total_arr > 0.0 else 100.0)
            else:
                # Fallback to match_rate for Greedy fallback
                revenue_score = float(metrics.get("match_rate", 0.0))
                
            summary = CandidatePlanSummary(
                profile=profile_name,
                objective_score=round(objective_score, 2),
                sla_score=round(sla_score, 2),
                revenue_score=round(revenue_score, 2),
                fairness_score=round(fairness_score, 2),
                workload_score=round(workload_score, 2),
                selected=selected,
                recommendation_reason=reason,
                rank=index + 1  # 1-indexed rank based on sorted order
            )
            summaries.append(summary)
            
        return summaries
