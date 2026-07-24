from app.agent.state import AgentState

async def generate_plans(state: AgentState) -> dict:
    """Graph node that executes solver optimization profiles."""
    print("[generate_plans]\nGenerating candidate scheduling options via CP-SAT solver...")
    dummy_plans = [
        {"plan_id": "PLAN-BALANCED", "profile": "Balanced", "objective_value": 85.0},
        {"plan_id": "PLAN-SLA", "profile": "SLA-First", "objective_value": 90.0}
    ]
    return {
        "candidate_plans": dummy_plans,
        "recommended_plan": dummy_plans[0],
        "status": "WAITING_FOR_APPROVAL"
    }
