import logging
from enum import Enum
from typing import Optional

from app.config.settings import settings

logger = logging.getLogger("core-api.config.preference_config")

class OptimizationProfile(str, Enum):
    BALANCED = "BALANCED"
    SLA_FIRST = "SLA_FIRST"
    REVENUE_FIRST = "REVENUE_FIRST"
    FAIRNESS_FIRST = "FAIRNESS_FIRST"

DEFAULT_PROFILE_EXPLANATIONS = {
    OptimizationProfile.BALANCED: "Best overall balance",
    OptimizationProfile.SLA_FIRST: "Highest SLA protection",
    OptimizationProfile.REVENUE_FIRST: "Highest revenue preservation",
    OptimizationProfile.FAIRNESS_FIRST: "Best workload distribution"
}

class PreferenceConfig:
    """Centralized configuration for the experimental Preference Memory and Personalized Recommendation system.
    
    Houses all constants, thresholds, weights, and normalization logic as a single source of truth.
    """
    # ── Learning Thresholds ──────────────────────────────────────────────────
    # Minimum runs required to transition out of COLD_START learning state
    COLD_START_RUNS = settings.cold_start_runs
    # Minimum runs required to transition into MATURE learning state
    MATURE_LEARNING_RUNS = settings.mature_learning_runs

    # ── Confidence Level Thresholds ──────────────────────────────────────────
    # Confidence score bounds determining low/medium/high confidence level enums
    CONFIDENCE_LOW_THRESHOLD = settings.preference_confidence_low_threshold
    CONFIDENCE_HIGH_THRESHOLD = settings.preference_confidence_high_threshold

    # ── Acceptance Logic Parameters ──────────────────────────────────────────
    # Minimum recommendations shown to apply the low acceptance rate warning template
    ACCEPTANCE_SHOWN_MIN = 3
    # Acceptance rate ratio below which confidence is flagged as limited
    ACCEPTANCE_LOW_RATIO_THRESHOLD = 0.50

    # ── Recommendation Scoring Weights ───────────────────────────────────────
    # Weights determining candidate preference_score from selection frequency vs current goal text matching
    PROFILE_WEIGHT = settings.preference_profile_weight
    GOAL_SIMILARITY_WEIGHT = settings.preference_goal_similarity_weight
    MAX_PREF_SCORE = 100.0

    # ── Confidence Score Weights ─────────────────────────────────────────────
    # Weights combining selection dominance and recommendation acceptance rate to calculate confidence
    DOMINANCE_FACTOR_WEIGHT = settings.preference_dominance_factor_weight
    ACCEPTANCE_FACTOR_WEIGHT = settings.preference_acceptance_factor_weight
    # Default acceptance rate assumed before any recommendations have been shown
    DEFAULT_ACCEPTANCE_RATE_BASELINE = 0.50

    @staticmethod
    def normalize_profile(profile_name: Optional[str]) -> OptimizationProfile:
        """Type-safely normalizes any input profile name string into an OptimizationProfile enum."""
        if not profile_name:
            return OptimizationProfile.BALANCED
        normalized = profile_name.strip().upper().replace("-", "_").replace(" ", "_")
        try:
            return OptimizationProfile(normalized)
        except ValueError:
            return OptimizationProfile.BALANCED
