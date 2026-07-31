import pytest
from datetime import datetime
from app.database.session import async_session
from app.database.models import ManagerPreference
from app.services.manager_preference_service import ManagerPreferenceService, PreferenceMemory
from app.services.preference_learning_engine import PreferenceLearningEngine
from app.agent.nodes.update_preference_memory import update_preference_memory
from sqlalchemy import delete
from unittest.mock import patch, MagicMock, AsyncMock

@pytest.mark.asyncio
async def test_preference_learning_engine_updates():
    """Verifies that the PreferenceLearningEngine correctly updates the statistics and extracts constraints."""
    memory = PreferenceMemory()
    
    # 1. Test first approval with no personalization shown
    updated = PreferenceLearningEngine.update_memory(
        memory=memory,
        approval_status="APPROVED",
        selected_profile="SLA First",
        goal_text="Please optimize SLA deadlines."
    )
    assert updated.total_runs == 1
    assert updated.profile_counts["SLA_FIRST"] == 1
    assert updated.recommendation_statistics.shown == 0
    
    # 2. Test second approval, this time with personalization shown and accepted
    updated = PreferenceLearningEngine.update_memory(
        memory=updated,
        approval_status="APPROVED",
        selected_profile="Balanced",
        personalized_profile="Balanced",
        goal_text="Standard run."
    )
    assert updated.total_runs == 2
    assert updated.profile_counts["BALANCED"] == 1
    assert updated.recommendation_statistics.shown == 1
    assert updated.recommendation_statistics.accepted == 1
    assert updated.recommendation_statistics.rejected == 0
    
    # 3. Test third approval, personalization shown but rejected (chose SLA First instead)
    updated = PreferenceLearningEngine.update_memory(
        memory=updated,
        approval_status="APPROVED",
        selected_profile="SLA First",
        personalized_profile="Balanced",
        goal_text="Protect renewals today."
    )
    assert updated.total_runs == 3
    assert updated.profile_counts["SLA_FIRST"] == 2
    assert updated.recommendation_statistics.shown == 2
    assert updated.recommendation_statistics.accepted == 1
    assert updated.recommendation_statistics.rejected == 1
    # Check that "Protect renewals" constraint was extracted
    assert "Protect renewals" in updated.learned_constraints
    
    # 4. Test modify request and constraint extraction
    updated = PreferenceLearningEngine.update_memory(
        memory=updated,
        approval_status="MODIFY",
        goal_text="Avoid Daniel overload please."
    )
    # total_runs does not increment for MODIFY, but rejection count on shown personalized recommendation does
    assert updated.total_runs == 3
    assert "Avoid Daniel overload" in updated.learned_constraints

@pytest.mark.asyncio
async def test_integration_lifecycle():
    """Verifies the complete integration lifecycle: Load default, update, save, reload, verify."""
    async with async_session() as session:
        async with session.begin():
            # Clear database table to ensure clean state
            await session.execute(delete(ManagerPreference))
            
            # 1. Load default memory
            mem = await ManagerPreferenceService.load_memory(session)
            assert mem.total_runs == 0
            assert mem.profile_counts == {}
            
            # 2. Update memory
            mem = PreferenceLearningEngine.update_memory(
                memory=mem,
                approval_status="APPROVED",
                selected_profile="SLA_FIRST",
                personalized_profile="BALANCED",
                goal_text="Protect renewals for banking clients."
            )
            
            # 3. Save memory
            success = await ManagerPreferenceService.save_memory(session, mem)
            assert success is True
            
            # 4. Reload memory
            reloaded = await ManagerPreferenceService.load_memory(session)
            
            # 5. Verify all values persisted correctly
            assert reloaded.total_runs == 1
            assert reloaded.profile_counts["SLA_FIRST"] == 1
            assert reloaded.recommendation_statistics.shown == 1
            assert reloaded.recommendation_statistics.rejected == 1
            assert "Protect renewals" in reloaded.learned_constraints
            assert "Prioritize banking customers" in reloaded.learned_constraints

@pytest.mark.asyncio
async def test_update_preference_memory_workflow_node():
    """Verifies that the update_preference_memory LangGraph node runs, loads, updates, and saves."""
    state = {
        "run_id": "RUN-TEST-NODE",
        "approval_status": "APPROVED",
        "recommended_plan": {"profile": "Balanced"},
        "personalized_recommendation": {"profile": "Balanced"},
        "goal_text": "Optimize SLA deadlines.",
        "decision_reason": "Best tradeoff for today's SLA risk.",
        "decision_source": "AI_RECOMMENDATION",
    }
    
    async with async_session() as session:
        async with session.begin():
            await session.execute(delete(ManagerPreference))
            
    # Mock persistence event and run updates so we don't pollute database events tables or trigger foreign keys issues
    with patch("app.agent.nodes.update_preference_memory.persistence") as mock_persistence:
        mock_persistence.save_run_event = AsyncMock()
        
        # Execute node
        node_update = await update_preference_memory(state)
        assert node_update == {
            "current_node": "update_preference_memory",
            "approval_status": "APPROVED",
            "modification_requested": False,
        }
        
        # Validate that database record was updated and saved
        async with async_session() as session:
            async with session.begin():
                mem = await ManagerPreferenceService.load_memory(session)
                assert mem.total_runs == 1
                assert mem.profile_counts["BALANCED"] == 1
                assert mem.recommendation_statistics.accepted == 1
                
        # Validate run event was published
        mock_persistence.save_run_event.assert_called_once()
        call_kwargs = mock_persistence.save_run_event.call_args.kwargs
        assert call_kwargs["event_type"] == "PREFERENCE_MEM_UPDATED"
        assert call_kwargs["run_id"] == "RUN-TEST-NODE"
        assert call_kwargs["payload_dict"]["decision_reason"] == "Best tradeoff for today's SLA risk."
        assert call_kwargs["payload_dict"]["decision_source"] == "AI_RECOMMENDATION"
