from app.agent.state import AgentState
from app.database.session import async_session
import app.database.persistence as persistence
from datetime import datetime

async def complete_run(state: AgentState) -> dict:
    run_id = state.get("run_id", "unknown")
    approval_status = state.get("approval_status")
    status = state.get("status")

    if status == "FAILED_SAGA":
        final_status = "FAILED_SAGA"
    elif status in {"FAILED", "FAILED_SAFE"} and approval_status != "REJECTED":
        final_status = "FAILED"
    else:
        final_status = "COMPLETED"

    print(f"[complete_run]\nRun closed with status {final_status}")

    updates = {"status": final_status}
    if approval_status == "APPROVED" and status == "EXECUTED":
        # 1. Update AgentState baseline snapshot (successful execution baseline)
        state["baseline_enterprise_snapshot"] = state.get("enterprise_state")
        updates["baseline_enterprise_snapshot"] = state.get("enterprise_state")
        
        # 2. Invoke Simulation Coordinator callback (best-effort notification)
        timeline_position = state.get("timeline_position") or 0
        payload = {
            "run_id": run_id,
            "scenario_id": state.get("scenario_id"),
            "timeline_position": timeline_position,
            "simulation_time": state.get("simulation_time"),
            "status": status
        }
        from app.services.simulation_coordinator import SimulationCoordinator
        try:
            await SimulationCoordinator.on_execution_complete(
                run_id=run_id,
                timeline_position=timeline_position,
                state=payload
            )
        except Exception as notifier_err:
            import logging
            logging.getLogger("core-api.nodes.complete_run").error(
                f"Failed to notify simulation coordinator: {notifier_err}",
                exc_info=True
            )
            
    checkpoint_data = dict(state)
    checkpoint_data["status"] = final_status
    event_type = "RUN_COMPLETED" if final_status == "COMPLETED" else "RUN_FAILED"
    event_summary = (
        "Agent execution run completed successfully"
        if final_status == "COMPLETED" and status == "EXECUTED"
        else "Decision route closed safely without execution"
        if final_status == "COMPLETED"
        else f"Agent execution stopped with status {final_status}"
    )
    
    async with async_session() as session:
        async with session.begin():
            await persistence.save_agent_run(
                session=session,
                run_id=run_id,
                scenario_id="phase2-demo",
                status=final_status,
                current_node="complete_run",
                completed_at=datetime.utcnow()
            )
            await persistence.save_graph_checkpoint(
                session=session,
                run_id=run_id,
                state_version=1,
                node_name="complete_run",
                checkpoint_json=checkpoint_data
            )
            await persistence.save_run_event(
                session=session,
                run_id=run_id,
                sequence_number=100,
                event_type=event_type,
                source="complete_run",
                summary=event_summary,
                state_version=1
            )
            
    return updates
