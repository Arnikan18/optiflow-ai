from app.agent.state import AgentState
from app.goals.interpreter import interpret_goal_text
from app.database.session import async_session
from app.llm_settings.service import llm_settings_service
import app.database.persistence as persistence

async def interpret_goal(state: AgentState) -> dict:
    goal_text = state.get("goal_text", "")
    run_id = state.get("run_id", "unknown")
    runtime = llm_settings_service.current()
    requested_provider = state.get("llm_provider")
    requested_model = state.get("llm_model")
    selected = runtime.provider_for(requested_provider, requested_model)
    selected_provider = selected[0] if selected else None
    selected_model = selected[1].model_name if selected else None
    structured_goal = interpret_goal_text(
        goal_text,
        runtime_settings=runtime,
        provider_name=requested_provider or selected_provider,
        model_name=requested_model or selected_model,
    )
    print("[interpret_goal]\nGoal interpreted")
    
    goal_id = f"G-{run_id}"
    structured_goal_dict = structured_goal.model_dump()
    
    async with async_session() as session:
        async with session.begin():
            await persistence.save_business_goal(
                session=session,
                goal_id=goal_id,
                original_text=goal_text,
                structured_goal_dict=structured_goal_dict,
                objective_profile=structured_goal.summary,
                time_horizon_minutes=structured_goal.time_horizon.value * 24 * 60 if structured_goal.time_horizon else None
            )
            await persistence.save_agent_run(
                session=session,
                run_id=run_id,
                scenario_id="phase2-demo",
                status="INTERPRETED",
                goal_text=goal_text,
                state_version=1,
                goal_id=goal_id,
                current_node="interpret_goal"
            )
            await persistence.save_run_event(
                session=session,
                run_id=run_id,
                sequence_number=2,
                event_type="GOAL_INTERPRETED",
                source="interpret_goal",
                summary="Goal successfully parsed to StructuredGoal configuration",
                payload_dict=structured_goal_dict,
                state_version=1
            )
            
    ret = {
        "structured_goal": structured_goal_dict,
        "llm_mode": "ai_assisted" if selected else "rules_only",
    }
    if selected_provider and selected_model:
        ret["llm_provider"] = selected_provider
        ret["llm_model"] = selected_model
    app_status = state.get("approval_status")
    if app_status not in ("APPROVED", "REJECTED"):
        ret["approval_status"] = "PENDING"
    return ret
