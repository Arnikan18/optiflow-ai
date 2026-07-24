from app.agent.state import AgentState

async def execute_tools(state: AgentState) -> dict:
    print("[execute_tools]\nTools executed")
    dummy_results = [
        {"tool": "crm-service", "status": "SUCCESS", "records_fetched": 4},
        {"tool": "incident-service", "status": "SUCCESS", "records_fetched": 4}
    ]
    return {"tool_results": dummy_results}
