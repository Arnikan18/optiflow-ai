from app.agent.state import AgentState

async def build_state(state: AgentState) -> dict:
    print("[build_state]\nEnterprise state built")
    dummy_state = {
        "snapshot_id": "SNAP-001",
        "state_version": 1,
        "customers": [],
        "escalations": [],
        "specialists": []
    }
    return {"enterprise_state": dummy_state}
