from app.agent.state import AgentState

async def pause_for_approval(state: AgentState) -> dict:
    """Graph node representing a safe pause state waiting for manager approval decision.
    
    If approval is not yet received, status remains 'WAITING_FOR_APPROVAL'
    and graph halts at this checkpoint.
    """
    print("[pause_for_approval]\nHalting run. Waiting for manager approval...")
    return {"approval_status": "PENDING"}
