import pytest
from datetime import datetime
from app.database.session import async_session
from app.database.models import ManagerPreference
from app.services.manager_preference_service import ManagerPreferenceService, PreferenceMemory, RecommendationStats
from sqlalchemy import delete

@pytest.mark.asyncio
async def test_load_preferences_default():
    """Verifies that load_memory returns a default PreferenceMemory when no database record exists."""
    async with async_session() as session:
        async with session.begin():
            # Clear database table to ensure clean state
            await session.execute(delete(ManagerPreference))
            
            prefs = await ManagerPreferenceService.load_memory(session)
            assert isinstance(prefs, PreferenceMemory)
            assert prefs.version == 1
            assert prefs.total_runs == 0
            assert prefs.profile_counts == {}
            assert prefs.recommendation_statistics.shown == 0
            assert prefs.learned_constraints == []

@pytest.mark.asyncio
async def test_save_and_load_preferences():
    """Verifies that saving preferences serializes correctly and loading parses it back exactly."""
    async with async_session() as session:
        async with session.begin():
            await session.execute(delete(ManagerPreference))
            
            # Create preference data
            prefs = PreferenceMemory(
                version=2,
                total_runs=10,
                profile_counts={"BALANCED": 5, "SLA_FIRST": 5},
                recommendation_statistics=RecommendationStats(
                    shown=4,
                    accepted=3,
                    rejected=1,
                    last_updated=datetime(2026, 7, 29, 20, 0, 0),
                    last_recommendation_timestamp=datetime(2026, 7, 29, 20, 0, 0)
                ),
                learned_constraints=["Avoid Daniel overload"]
            )
            
            # Save
            success = await ManagerPreferenceService.save_memory(session, prefs)
            assert success is True
            
            # Load and verify
            loaded_prefs = await ManagerPreferenceService.load_memory(session)
            assert loaded_prefs is not None
            assert loaded_prefs.version == 2
            assert loaded_prefs.total_runs == 10
            assert loaded_prefs.profile_counts["BALANCED"] == 5
            assert loaded_prefs.recommendation_statistics.shown == 4
            assert loaded_prefs.recommendation_statistics.accepted == 3
            assert loaded_prefs.recommendation_statistics.rejected == 1
            assert loaded_prefs.learned_constraints == ["Avoid Daniel overload"]
            assert loaded_prefs.updated_at is not None

@pytest.mark.asyncio
async def test_load_preferences_malformed_fallback():
    """Verifies that load_memory logs a warning and returns default PreferenceMemory if data is malformed."""
    async with async_session() as session:
        async with session.begin():
            await session.execute(delete(ManagerPreference))
            
            # Insert invalid JSON structure directly using models
            from app.database.persistence import save_manager_preference
            # Missing required types or completely invalid structure
            await save_manager_preference(session, {"version": "invalid-int-type", "total_runs": "not-an-int"})
            
            loaded_prefs = await ManagerPreferenceService.load_memory(session)
            assert isinstance(loaded_prefs, PreferenceMemory)
            # Should fallback to defaults
            assert loaded_prefs.version == 1
            assert loaded_prefs.total_runs == 0
