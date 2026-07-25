from app.agent.state import AgentState
from app.database.session import async_session
import app.database.persistence as persistence

async def pause_for_approval(state: AgentState) -> dict:
    """Graph node representing a safe pause state waiting for manager approval decision.
    
    If approval is not yet received, status remains 'WAITING_FOR_APPROVAL'
    and graph halts at this checkpoint.
    """
    app_status = state.get("approval_status")
    if app_status == "APPROVED":
        print("[pause_for_approval] Resuming: Approval status is APPROVED. Bypassing halt.")
        return {"status": "EXECUTING"}
        
    print("[pause_for_approval]\nHalting run. Waiting for manager approval...")
    
    run_id = state.get("run_id", "unknown")
    checkpoint_data = dict(state)
    checkpoint_data["status"] = "WAITING_FOR_APPROVAL"
    checkpoint_data["approval_status"] = "PENDING"
    
    async with async_session() as session:
        async with session.begin():
            await persistence.save_agent_run(
                session=session,
                run_id=run_id,
                scenario_id="phase2-demo",
                status="WAITING_FOR_APPROVAL",
                current_node="pause_for_approval"
            )
            await persistence.save_graph_checkpoint(
                session=session,
                run_id=run_id,
                state_version=1,
                node_name="pause_for_approval",
                checkpoint_json=checkpoint_data
            )
            await persistence.save_run_event(
                session=session,
                run_id=run_id,
                sequence_number=10,
                event_type="WAITING_FOR_APPROVAL",
                source="pause_for_approval",
                summary="Graph execution halted. Waiting for manager plan approval decision.",
                state_version=1
            )
            
    return {"approval_status": "PENDING", "status": "WAITING_FOR_APPROVAL"}
