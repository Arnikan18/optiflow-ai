from app.agent.state import AgentState
from app.goals.interpreter import interpret_goal_text
from app.database.session import async_session
import app.database.persistence as persistence

async def interpret_goal(state: AgentState) -> dict:
    goal_text = state.get("goal_text", "")
    run_id = state.get("run_id", "unknown")
    structured_goal = interpret_goal_text(goal_text)
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
            
    ret = {"structured_goal": structured_goal_dict}
    app_status = state.get("approval_status")
    if app_status not in ("APPROVED", "REJECTED"):
        ret["approval_status"] = "PENDING"
    return ret
