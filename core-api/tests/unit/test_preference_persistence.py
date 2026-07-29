import pytest
from app.database.session import async_session
from app.database.persistence import get_manager_preference, save_manager_preference

@pytest.mark.asyncio
async def test_manager_preference_crud():
    """Verifies that manager preference records can be created, retrieved, and updated in the database."""
    async with async_session() as session:
        async with session.begin():
            # 1. Verify retrieval of a non-existent record returns None
            # Note: We clear the table first if any existed from previous tests, or we just query id=1
            from sqlalchemy import delete
            from app.database.models import ManagerPreference
            await session.execute(delete(ManagerPreference))
            
            pref = await get_manager_preference(session)
            assert pref is None
            
            # 2. Verify creation of a new preference record
            test_data = {
                "version": 1,
                "total_runs": 2,
                "profile_counts": {"BALANCED": 1, "SLA_FIRST": 1},
                "recommendation_statistics": {
                    "shown": 2,
                    "accepted": 1,
                    "rejected": 1,
                    "last_updated": "2026-07-29T20:51:27Z",
                    "last_recommendation_timestamp": "2026-07-29T20:51:27Z"
                },
                "learned_constraints": ["Avoid Daniel overload"],
                "updated_at": "2026-07-29T20:51:27Z"
            }
            
            saved = await save_manager_preference(session, test_data)
            assert saved.id == 1
            assert saved.preference_json == test_data
            assert saved.updated_at is not None
            
            # 3. Verify retrieval of the created record
            fetched = await get_manager_preference(session)
            assert fetched is not None
            assert fetched.id == 1
            assert fetched.preference_json == test_data
            
            # 4. Verify updating the existing record
            updated_data = test_data.copy()
            updated_data["total_runs"] = 3
            updated_data["profile_counts"]["SLA_FIRST"] = 2
            
            updated = await save_manager_preference(session, updated_data)
            assert updated.id == 1
            assert updated.preference_json == updated_data
            
            fetched_updated = await get_manager_preference(session)
            assert fetched_updated is not None
            assert fetched_updated.preference_json == updated_data
            assert fetched_updated.preference_json["total_runs"] == 3

