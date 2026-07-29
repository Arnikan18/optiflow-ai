import logging
from app.agent.state import AgentState
from app.optimizer.solver import generate_optimization_plans
from app.optimizer.explainer import explain_plan
from app.config.settings import settings
from app.database.session import async_session
import app.database.persistence as persistence

logger = logging.getLogger("core-api.nodes.generate_plans")

async def generate_plans(state: AgentState) -> dict:
    """Graph node that executes solver optimization profiles using dynamic database records."""
    print("[generate_plans]\nGenerating candidate scheduling options via custom priority solver...")
    
    ent_state = state.get("enterprise_state") or {}
    run_id = state.get("run_id", "unknown")
    replan_count = int(state.get("replan_count") or 0)
    excluded_pairs = list(state.get("excluded_specialist_incidents") or [])
    
    # Guard: prevent infinite replan loops.
    if replan_count > settings.max_replan_count:
        logger.warning(f"[generate_plans] Replan limit ({settings.max_replan_count}) reached for run {run_id}. Forcing completion.")
        return {
            "candidate_plans": [],
            "recommended_plan": None,
            "status": "FAILED_SAGA",
            "replan_count": replan_count
        }
    
    customers = ent_state.get("customers", [])
    escalations = ent_state.get("escalations", [])
    specialists = ent_state.get("specialists", [])
    
    # Generate plans — pass exclusion constraints so CP-SAT avoids rejected pairs.
    plans = generate_optimization_plans(customers, escalations, specialists, excluded_pairs=excluded_pairs)
    
    # Generate natural language justifications for each computed plan
    for plan in plans:
        plan["explanation"] = explain_plan(
            plan["profile"],
            plan,
            ent_state,
            provider_name=state.get("llm_provider"),
            model_name=state.get("llm_model"),
        )
        
    # Recommend the plan with the highest objective value
    recommended = max(plans, key=lambda p: p["objective_value"]) if plans else None
    recommended_id = recommended["plan_id"] if recommended else None
    
    async with async_session() as session:
        async with session.begin():
            await persistence.save_agent_run(
                session=session,
                run_id=run_id,
                scenario_id="phase2-demo",
                status="WAITING_FOR_APPROVAL",
                current_node="generate_plans",
                recommended_plan_id=recommended_id,
                replan_count=replan_count
            )
            # Check if a fallback occurred
            fallback_occurred = any(p.get("metadata", {}).get("fallback_status") for p in plans)
            if fallback_occurred:
                await persistence.save_run_event(
                    session=session,
                    run_id=run_id,
                    sequence_number=4,
                    event_type="SOLVER_FALLBACK",
                    source="generate_plans",
                    summary="Primary CP-SAT solver failed or timed out. Transparently fell back to Greedy Optimizer.",
                    payload_dict={},
                    state_version=1
                )
                
            await persistence.save_run_event(
                session=session,
                run_id=run_id,
                sequence_number=5,
                event_type="PLANS_GENERATED",
                source="generate_plans",
                summary=f"Scheduling candidate profiles computed (replan #{replan_count}). {len(excluded_pairs)} pair(s) excluded.",
                payload_dict={
                    "plans_summary": [{"plan_id": p["plan_id"], "objective": p["objective_value"], "allocations": len(p.get("allocations", []))} for p in plans],
                    "excluded_pairs": excluded_pairs,
                    "replan_count": replan_count
                },
                state_version=1
            )
            
    return {
        "candidate_plans": plans,
        "recommended_plan": recommended,
        "status": "WAITING_FOR_APPROVAL",
        "replan_count": replan_count
    }

