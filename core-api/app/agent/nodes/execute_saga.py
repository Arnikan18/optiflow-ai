import logging
import asyncio
from app.agent.state import AgentState
from app.adapters.tool_client import ToolClient
from app.database.session import async_session
import app.database.persistence as persistence

logger = logging.getLogger("core-api.nodes.execute_saga")

async def execute_saga(state: AgentState) -> dict:
    """Graph node managing the transactional SAGA writes back to microservices."""
    print("[execute_saga]\nExecuting tentative reservation locks, assignments, and alerts...")
    
    run_id = state.get("run_id", "unknown")
    recommended = state.get("recommended_plan") or {}
    allocations = recommended.get("allocations", [])
    
    client = ToolClient(request_id=run_id)
    
    # Trace trackers for rollback
    created_reservations = []
    updated_incidents = []
    execution_actions = []
    execution_receipts = []
    
    saga_failed = False
    failure_reason = ""
    
    for alloc in allocations:
        inc_id = alloc.get("incident_id")
        spec_id = alloc.get("specialist_id")
        
        if not inc_id or not spec_id:
            continue
            
        res_id = f"RES-{run_id[:8]}-{inc_id[:8]}"
        req_id = f"REQ-{run_id[:8]}-{inc_id[:8]}"
        
        try:
            # 1. STEP A: Workforce Reservation
            print(f"  [SAGA] Reserving slot {res_id} for specialist {spec_id} on incident {inc_id}...")
            await client.create_reservation(
                reservation_id=res_id,
                specialist_id=spec_id,
                incident_id=inc_id,
                expires_in_seconds=300
            )
            created_reservations.append(res_id)
            
            # Confirm reservation to finalize it
            await client.confirm_reservation(reservation_id=res_id)
            execution_actions.append({"action": "RESERVE_CONFIRM", "entity": "workforce-service", "id": res_id})
            
            # 2. STEP B: Incident assignment
            print(f"  [SAGA] Assigning incident {inc_id} to specialist {spec_id}...")
            await client.assign_incident_specialist(incident_id=inc_id, specialist_id=spec_id)
            await client.patch_incident_status(incident_id=inc_id, incident_status="ASSIGNED")
            updated_incidents.append(inc_id)
            execution_actions.append({"action": "ASSIGN_INCIDENT", "entity": "incident-service", "id": inc_id})
            
            # 3. STEP C: Communication notifications
            print(f"  [SAGA] Dispatching notification request {req_id}...")
            await client.create_assignment_request(
                request_id=req_id,
                incident_id=inc_id,
                specialist_id=spec_id,
                message=f"OptiFlow Assignment: Please review SLA Escalation {inc_id} immediately.",
                expires_in_seconds=300
            )
            execution_actions.append({"action": "CREATE_NOTIFICATION", "entity": "communication-service", "id": req_id})
            
            execution_receipts.append({
                "receipt_id": f"REC-{run_id[:8]}-{inc_id[:8]}",
                "allocation": alloc,
                "status": "SUCCESS",
                "actions": ["RESERVE", "CONFIRM", "ASSIGN", "NOTIFY"]
            })
            
        except Exception as e:
            logger.warning(f"Saga execution failed for allocation {alloc}: {str(e)}")
            saga_failed = True
            failure_reason = f"Failure on ticket allocation {inc_id}: {str(e)}"
            break
            
    # SAGA Rollback / Compensating Transaction
    if saga_failed:
        print(f"\n[SAGA ROLLBACK] Triggering compensation workflows due to: {failure_reason}")
        
        # A. Undo workforce locks
        for r_id in created_reservations:
            try:
                print(f"  [ROLLBACK] Cancelling reservation {r_id}...")
                await client.cancel_reservation(reservation_id=r_id)
            except Exception as re:
                logger.error(f"Saga compensating reservation cancel failed for {r_id}: {str(re)}")
                
        # B. Undo incident status
        for i_id in updated_incidents:
            try:
                print(f"  [ROLLBACK] Resetting incident {i_id} to UNASSIGNED...")
                await client.assign_incident_specialist(incident_id=i_id, specialist_id="")
                await client.patch_incident_status(incident_id=i_id, incident_status="OPEN")
            except Exception as ie:
                logger.error(f"Saga compensating incident reset failed for {i_id}: {str(ie)}")
                
        status_outcome = "FAILED_SAGA"
    else:
        status_outcome = "EXECUTED"
        
    # Write SAGA outputs to database
    async with async_session() as session:
        async with session.begin():
            await persistence.save_agent_run(
                session=session,
                run_id=run_id,
                scenario_id="phase2-demo",
                status=status_outcome,
                current_node="execute_saga"
            )
            await persistence.save_run_event(
                session=session,
                run_id=run_id,
                sequence_number=50,
                event_type="SAGA_COMPLETED" if not saga_failed else "SAGA_FAILED",
                source="execute_saga",
                summary=f"Saga execution loop resolved: {status_outcome}. {failure_reason}",
                payload_dict={"receipts": execution_receipts, "actions_attempted": execution_actions},
                state_version=1
            )
            
    return {
        "execution_actions": execution_actions,
        "execution_receipts": execution_receipts,
        "status": status_outcome
    }
