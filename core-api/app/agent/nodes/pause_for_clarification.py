from app.agent.state import AgentState
from app.database.session import async_session
import app.database.persistence as persistence

async def pause_for_clarification(state: AgentState) -> dict:
    """Graph node representing a safe pause state waiting for manager clarification.
    
    In a live execution, the run status updates to 'WAITING_FOR_CLARIFICATION'
    and graph execution stops until resume input is supplied.
    """
    print("[pause_for_clarification]\nWaiting for manager clarification response...")
    
    run_id = state.get("run_id", "unknown")
    checkpoint_data = dict(state)
    checkpoint_data["status"] = "WAITING_FOR_CLARIFICATION"
    
    async with async_session() as session:
        async with session.begin():
            await persistence.save_agent_run(
                session=session,
                run_id=run_id,
                scenario_id="phase2-demo",
                status="WAITING_FOR_CLARIFICATION",
                current_node="pause_for_clarification"
            )
            await persistence.save_graph_checkpoint(
                session=session,
                run_id=run_id,
                state_version=1,
                node_name="pause_for_clarification",
                checkpoint_json=checkpoint_data
            )
            await persistence.save_run_event(
                session=session,
                run_id=run_id,
                sequence_number=11,
                event_type="WAITING_FOR_CLARIFICATION",
                source="pause_for_clarification",
                summary="Graph execution halted. Waiting for manager input to resolve validation clarifications.",
                state_version=1
            )
            
    return {"status": "WAITING_FOR_CLARIFICATION"}
