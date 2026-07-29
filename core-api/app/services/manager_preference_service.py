import logging
from datetime import datetime
from typing import Dict, List, Any, Optional
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.persistence import get_manager_preference, save_manager_preference

logger = logging.getLogger("core-api.services.manager_preference_service")

class RecommendationStats(BaseModel):
    shown: int = 0
    accepted: int = 0
    rejected: int = 0
    last_updated: Optional[datetime] = None
    last_recommendation_timestamp: Optional[datetime] = None

class PreferenceMemory(BaseModel):
    version: int = 1
    total_runs: int = 0
    profile_counts: Dict[str, int] = Field(default_factory=dict)
    recommendation_statistics: RecommendationStats = Field(default_factory=RecommendationStats)
    learned_constraints: List[str] = Field(default_factory=list)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class ManagerPreferenceService:
    """Persistence Service for Manager Preferences.
    
    Responsibilities:
    - CRUD database loading and saving of preferences.
    - Serialization/deserialization and Pydantic validation checks.
    
    Intentionally does NOT do:
    - Learning or decision statistics calculation (delegated to PreferenceLearningEngine).
    - Preference score computation and candidate ranking (delegated to RecommendationEngine).
    - Text explanation generation or status enum mapping (delegated to ExplanationEngine).
    """
    @staticmethod
    async def load_memory(session: AsyncSession) -> PreferenceMemory:
        """Loads and deserializes manager preferences from the database.
        
        If no preferences exist yet, returns an initialized default instance.
        """
        try:
            pref = await get_manager_preference(session)
            if pref and pref.preference_json:
                return PreferenceMemory.model_validate(pref.preference_json)
        except Exception as e:
            logger.warning("Failed to load preference memory; falling back to default. Error: %s", str(e))
        return PreferenceMemory()

    @staticmethod
    async def save_memory(session: AsyncSession, preferences: PreferenceMemory) -> bool:
        """Serializes and persists the manager preferences to the database."""
        try:
            preferences.updated_at = datetime.utcnow()
            dumped = preferences.model_dump(mode="json")
            await save_manager_preference(session, dumped)
            return True
        except Exception as e:
            logger.error("Failed to save preference memory: %s", str(e))
            return False

