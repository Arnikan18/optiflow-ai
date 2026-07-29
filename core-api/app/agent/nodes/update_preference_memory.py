import logging
from app.agent.state import AgentState
from app.database.session import async_session
import app.database.persistence as persistence
from app.services.manager_preference_service import ManagerPreferenceService
from app.services.preference_learning_engine import PreferenceLearningEngine

logger = logging.getLogger("core-api.nodes.update_preference_memory")

async def update_preference_memory(state: AgentState) -> dict:
    """Graph node that updates manager preference memory based on approval/rejection decisions.
    
    Loads current memory, executes PreferenceLearningEngine logic, persists updates,
    and publishes a PREFERENCE_MEM_UPDATED run event.
    """
    run_id = state.get("run_id", "unknown")
    approval_status = state.get("approval_status")
    recommended_plan = state.get("recommended_plan") or {}
    personalized_rec = state.get("personalized_recommendation") or {}
    goal_text = state.get("goal_text")
    
    selected_profile = recommended_plan.get("profile")
    personalized_profile = personalized_rec.get("profile")
    
    print(f"[update_preference_memory] Resumed. Decision: {approval_status}, Profile: {selected_profile}")
    
    async with async_session() as session:
        async with session.begin():
            # 1. Load preference memory from DB
            memory = await ManagerPreferenceService.load_memory(session)
            
            # 2. Update memory via learning engine
            updated_memory = PreferenceLearningEngine.update_memory(
                memory=memory,
                approval_status=approval_status,
                selected_profile=selected_profile,
                personalized_profile=personalized_profile,
                goal_text=goal_text
            )
            
            # 3. Save memory back to DB
            await ManagerPreferenceService.save_memory(session, updated_memory)
            
            # 4. Save a run event for explainability/audit trail
            await persistence.save_run_event(
                session=session,
                run_id=run_id,
                sequence_number=11,
                event_type="PREFERENCE_MEM_UPDATED",
                source="update_preference_memory",
                summary=f"Preference memory updated: total runs = {updated_memory.total_runs}, profile selection count incremented.",
                payload_dict={
                    "decision": approval_status,
                    "selected_profile": selected_profile,
                    "personalized_profile": personalized_profile,
                    "total_runs": updated_memory.total_runs,
                    "profile_counts": updated_memory.profile_counts,
                    "learned_constraints": updated_memory.learned_constraints
                },
                state_version=1
            )
            
    # Return state update. LangGraph updates the state dictionary with returned values.
    # Note: we do not change the state's status/node here because route_after_preference_update
    # will handle routing to subsequent nodes.
    return {
        "current_node": "update_preference_memory"
    }
