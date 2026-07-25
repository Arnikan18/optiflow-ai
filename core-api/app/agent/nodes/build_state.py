from app.agent.state import AgentState

from datetime import datetime
from app.database.session import async_session
import app.database.persistence as persistence

async def build_state(state: AgentState) -> dict:
    print("[build_state]\nEnterprise state built")
    
    crm_res = {}
    incident_res = {}
    workforce_res = {}
    communication_res = {}
    
    tool_results = state.get("tool_results", [])
    for tr in tool_results:
        tool = tr.get("tool")
        data = tr.get("data", {})
        if tool == "crm-service":
            crm_res = data
        elif tool == "incident-service":
            incident_res = data
        elif tool == "workforce-service":
            workforce_res = data
        elif tool == "communication-service":
            communication_res = data
            
    # Normalize collections
    customers = crm_res.get("customers", []) if isinstance(crm_res, dict) else []
    escalations = incident_res.get("incidents", []) if isinstance(incident_res, dict) else []
    specialists = workforce_res.get("specialists", []) if isinstance(workforce_res, dict) else []
    assignment_requests = communication_res.get("assignment_requests", []) if isinstance(communication_res, dict) else []
    
    run_id = state.get("run_id", "RUN-UNKNOWN")
    retrieved_time = datetime.utcnow().isoformat()
    
    collected_evidence = []
    
    # 1. CRM Evidence
    for cus in customers:
        collected_evidence.append({
            "evidence_id": f"EV-{run_id}-CRM-{cus.get('customer_id', 'UNKNOWN')}",
            "run_id": run_id,
            "evidence_type": "CUSTOMER_IDENTITY",
            "entity_type": "CUSTOMER",
            "entity_id": cus.get("customer_id"),
            "source_tool": "crm-service",
            "source_record_id": cus.get("customer_id"),
            "payload": cus,
            "retrieved_at": retrieved_time,
            "confidence_level": "HIGH",
            "freshness_status": "FRESH"
        })
        
    # 2. Incident Evidence
    for inc in escalations:
        collected_evidence.append({
            "evidence_id": f"EV-{run_id}-INC-{inc.get('incident_id', 'UNKNOWN')}",
            "run_id": run_id,
            "evidence_type": "ACTIVE_ESCALATIONS",
            "entity_type": "INCIDENT",
            "entity_id": inc.get("incident_id"),
            "source_tool": "incident-service",
            "source_record_id": inc.get("incident_id"),
            "payload": inc,
            "retrieved_at": retrieved_time,
            "confidence_level": "HIGH",
            "freshness_status": "FRESH"
        })
        
    # 3. Specialist Evidence
    for spec in specialists:
        collected_evidence.append({
            "evidence_id": f"EV-{run_id}-WRK-{spec.get('specialist_id', 'UNKNOWN')}",
            "run_id": run_id,
            "evidence_type": "SPECIALIST_SKILLS",
            "entity_type": "SPECIALIST",
            "entity_id": spec.get("specialist_id"),
            "source_tool": "workforce-service",
            "source_record_id": spec.get("specialist_id"),
            "payload": spec,
            "retrieved_at": retrieved_time,
            "confidence_level": "HIGH",
            "freshness_status": "FRESH"
        })

    # Cache unified database snapshot structure for planner evaluation
    enterprise_state = {
        "snapshot_id": f"SNAP-{run_id}",
        "state_version": state.get("state_version", 1),
        "customers": customers,
        "escalations": escalations,
        "specialists": specialists,
        "assignment_requests": assignment_requests
    }
    
    async with async_session() as session:
        async with session.begin():
            await persistence.save_evidence_items(session, run_id, 1, collected_evidence)
            await persistence.save_state_snapshot(session, run_id, 1, enterprise_state)
            await persistence.save_agent_run(
                session=session,
                run_id=run_id,
                scenario_id="phase2-demo",
                status="STATE_BUILT",
                current_node="build_state"
            )
            await persistence.save_run_event(
                session=session,
                run_id=run_id,
                sequence_number=4,
                event_type="STATE_BUILT",
                source="build_state",
                summary="Unified database snapshot state cache successfully constructed and saved",
                state_version=1
            )
            
    return {
        "enterprise_state": enterprise_state,
        "collected_evidence": collected_evidence
    }
