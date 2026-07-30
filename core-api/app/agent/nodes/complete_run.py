from app.agent.state import AgentState
from app.database.session import async_session
import app.database.persistence as persistence
from datetime import datetime

async def complete_run(state: AgentState) -> dict:
    print("[complete_run]\nRun completed")
    
    run_id = state.get("run_id", "unknown")
    approval_status = state.get("approval_status")
    status = state.get("status")
    
    if approval_status == "APPROVED" and status == "EXECUTED":
        # 1. Update AgentState baseline snapshot (successful execution baseline)
        state["baseline_enterprise_snapshot"] = state.get("enterprise_state")
        
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
    checkpoint_data["status"] = "COMPLETED"
    
    async with async_session() as session:
        async with session.begin():
            await persistence.save_agent_run(
                session=session,
                run_id=run_id,
                scenario_id="phase2-demo",
                status="COMPLETED",
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
                event_type="RUN_COMPLETED",
                source="complete_run",
                summary="Agent execution run completed successfully",
                state_version=1
            )
            
    return {"status": "COMPLETED"}
