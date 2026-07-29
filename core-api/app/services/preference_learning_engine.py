import logging
from datetime import datetime
from typing import Optional, List
from app.config.preference_config import PreferenceConfig, OptimizationProfile
from app.services.manager_preference_service import PreferenceMemory, RecommendationStats

logger = logging.getLogger("core-api.services.preference_learning_engine")

class PreferenceLearningEngine:
    """Learning Engine for Manager Preferences.
    
    Responsibilities:
    - Increments profile counts, total runs, and recommendation accept/reject metrics.
    - Extracts heuristic constraints from goal texts and modification requests.
    
    Intentionally does NOT do:
    - Persist memory to database (delegated to ManagerPreferenceService).
    - Compute scoring, rank candidate plans, or generate text explanations.
    """
    @staticmethod
    def update_memory(
        memory: PreferenceMemory,
        approval_status: str,
        selected_profile: Optional[str] = None,
        personalized_profile: Optional[str] = None,
        goal_text: Optional[str] = None
    ) -> PreferenceMemory:
        """Updates the PreferenceMemory based on manager decisions, selection profile, and goal text constraints.
        
        Isolates stats increments and constraint extraction from the database persistence layers.
        """
        now = datetime.utcnow()
        memory.updated_at = now
        
        # 1. Handle constraints extraction if goal_text is provided
        if goal_text:
            normalized_goal = goal_text.lower()
            if "renew" in normalized_goal and "Protect renewals" not in memory.learned_constraints:
                memory.learned_constraints.append("Protect renewals")
            if "daniel" in normalized_goal and "Avoid Daniel overload" not in memory.learned_constraints:
                memory.learned_constraints.append("Avoid Daniel overload")
            if "banking" in normalized_goal and "Prioritize banking customers" not in memory.learned_constraints:
                memory.learned_constraints.append("Prioritize banking customers")
                
            # Fallback: if it's a short custom goal that doesn't match predefined rules, we can add it directly
            # to capture novel natural language constraints.
            cleaned_goal = goal_text.strip()
            if len(cleaned_goal) < 60 and cleaned_goal not in memory.learned_constraints:
                # Avoid duplicates and check if not already covered by matched rules
                if not any(kw in normalized_goal for kw in ["renew", "daniel", "banking"]):
                    memory.learned_constraints.append(cleaned_goal)

        # 2. Handle Decision type updates
        if approval_status == "APPROVED":
            memory.total_runs += 1
            
            # Increment profile count if profile was selected
            if selected_profile:
                # Normalize profile name using PreferenceConfig helper to get enum
                norm_profile = PreferenceConfig.normalize_profile(selected_profile)
                memory.profile_counts[norm_profile.value] = memory.profile_counts.get(norm_profile.value, 0) + 1
            
            # Update recommendation stats if a personalization recommendation was shown
            if personalized_profile:
                memory.recommendation_statistics.shown += 1
                memory.recommendation_statistics.last_recommendation_timestamp = now
                
                # Check if user accepted the recommendation
                norm_selected = PreferenceConfig.normalize_profile(selected_profile) if selected_profile else None
                norm_personalized = PreferenceConfig.normalize_profile(personalized_profile)
                
                if norm_selected == norm_personalized:
                    memory.recommendation_statistics.accepted += 1
                else:
                    memory.recommendation_statistics.rejected += 1
                    
            memory.recommendation_statistics.last_updated = now

        elif approval_status == "REJECTED":
            memory.total_runs += 1
            
            # If a recommendation was shown and they rejected everything, it counts as a rejected recommendation
            if personalized_profile:
                memory.recommendation_statistics.shown += 1
                memory.recommendation_statistics.rejected += 1
                memory.recommendation_statistics.last_recommendation_timestamp = now
                
            memory.recommendation_statistics.last_updated = now
            
        elif approval_status == "MODIFY":
            # If they choose to modify, we don't complete the run, but we can treat it as a rejected recommendation
            if personalized_profile:
                memory.recommendation_statistics.shown += 1
                memory.recommendation_statistics.rejected += 1
                memory.recommendation_statistics.last_recommendation_timestamp = now
                
            memory.recommendation_statistics.last_updated = now

        return memory
