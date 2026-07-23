from app.agent.state import AgentState

async def complete_run(state: AgentState) -> dict:
    print("[complete_run]\nRun completed")
    return {"status": "COMPLETED"}
