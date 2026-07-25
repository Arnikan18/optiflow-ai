from app.agent.state import AgentState
from app.database.session import async_session
import app.database.persistence as persistence

async def receive_goal(state: AgentState) -> dict:
    run_id = state.get("run_id", "unknown")
    goal_text = state.get("goal_text", "")
    print(f"[receive_goal]\nRun: {run_id}")
    
    async with async_session() as session:
        async with session.begin():
            await persistence.save_agent_run(
                session=session,
                run_id=run_id,
                scenario_id="phase2-demo",
                status="RECEIVED",
                goal_text=goal_text,
                state_version=1,
                current_node="receive_goal"
            )
            await persistence.save_run_event(
                session=session,
                run_id=run_id,
                sequence_number=1,
                event_type="RUN_STARTED",
                source="receive_goal",
                summary="Agent execution run started",
                state_version=1
            )
            
    return {"status": "RECEIVED"}
