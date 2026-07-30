from app.agent.state import AgentState
from app.services.enterprise_monitor import EnterpriseMonitor

async def enterprise_monitor(state: AgentState) -> dict:
    """LangGraph node wrapping the EnterpriseMonitor decision logic."""
    print("[enterprise_monitor] Evaluating operational changes...")
    
    # Extract metadata
    latest_event = state.get("latest_event")
    baseline = state.get("baseline_enterprise_snapshot")
    current_state = state.get("enterprise_state") or {}
    
    # Calculate decision
    replan_needed = EnterpriseMonitor.should_replan(
        event=latest_event,
        baseline_snapshot=baseline,
        current_state=current_state
    )
    
    print(f"[enterprise_monitor] Replan needed: {replan_needed}")
    return {"replan_needed": replan_needed}
