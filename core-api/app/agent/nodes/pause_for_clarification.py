from app.agent.state import AgentState

async def pause_for_clarification(state: AgentState) -> dict:
    """Graph node representing a safe pause state waiting for manager clarification.
    
    In a live execution, the run status updates to 'WAITING_FOR_CLARIFICATION'
    and graph execution stops until resume input is supplied.
    """
    print("[pause_for_clarification]\nWaiting for manager clarification response...")
    return {"status": "WAITING_FOR_CLARIFICATION"}
