from app.agent.state import AgentState

async def receive_goal(state: AgentState) -> dict:
    run_id = state.get("run_id", "unknown")
    print(f"[receive_goal]\nRun: {run_id}")
    return {"status": "RECEIVED"}
