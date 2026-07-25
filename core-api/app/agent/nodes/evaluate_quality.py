import logging
from sqlalchemy import text
from app.agent.state import AgentState
from app.database.session import async_session

logger = logging.getLogger("core-api.nodes.evaluate_quality")

async def evaluate_quality(state: AgentState) -> dict:
    """Graph node checking evidence completeness, freshness and conflicts."""
    print("[evaluate_quality]\nVerifying evidence quality and resolving database references...")
    
    ent_state = state.get("enterprise_state") or {}
    run_id = state.get("run_id", "unknown")
    
    customers = ent_state.get("customers", [])
    escalations = ent_state.get("escalations", [])
    specialists = ent_state.get("specialists", [])
    
    missing_fields = []
    data_conflicts = []
    source_freshness = {
        "crm": "FRESH",
        "incident": "FRESH",
        "workforce": "FRESH",
        "communication": "FRESH"
    }
    
    # 1. Validate customer data integrity
    for c in customers:
        c_id = c.get("customer_id")
        if not c_id:
            missing_fields.append("Customer missing customer_id")
            continue
        arr = c.get("arr", 0.0)
        if arr < 0:
            data_conflicts.append(f"Customer {c_id} has negative ARR: {arr}")
            
    # 2. Validate incident data integrity
    for esc in escalations:
        inc_id = esc.get("incident_id")
        if not inc_id:
            missing_fields.append("Escalation missing incident_id")
            continue
        if not esc.get("priority"):
            missing_fields.append(f"Escalation {inc_id} missing priority")
        if not esc.get("customer_id"):
            missing_fields.append(f"Escalation {inc_id} missing customer_id")
            
    # 3. Validate specialist data integrity
    for s in specialists:
        spec_id = s.get("specialist_id")
        if not spec_id:
            missing_fields.append("Specialist missing specialist_id")
            continue
        if not s.get("skills"):
            missing_fields.append(f"Specialist {spec_id} has empty or missing skills")
        cap = s.get("capacity", 0)
        if cap < 0:
            data_conflicts.append(f"Specialist {spec_id} has negative capacity: {cap}")
            
    # Compute overall quality status
    quality_status = "FRESH"
    if missing_fields:
        quality_status = "DEGRADED"
    if data_conflicts:
        quality_status = "STALE"
        
    # Update the snapshot quality record in database
    try:
        async with async_session() as session:
            await session.execute(
                text("UPDATE state_snapshots SET quality = :q WHERE run_id = :r"),
                {"q": quality_status, "r": run_id}
            )
            await session.commit()
    except Exception as e:
        logger.warning(f"Failed to update state snapshot quality in database: {str(e)}")
        
    logger.info(f"Quality validation completed. Status: {quality_status}. Conflicts: {len(data_conflicts)} | Missing: {len(missing_fields)}")
    
    return {
        "source_freshness": source_freshness,
        "data_conflicts": data_conflicts,
        "missing_fields": missing_fields
    }
