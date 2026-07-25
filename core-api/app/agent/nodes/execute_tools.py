import asyncio
import logging
from app.agent.state import AgentState
from app.adapters.tool_client import ToolClient

logger = logging.getLogger("core-api.nodes.execute_tools")

# Static fallback data in case microservices are offline/erroring
FALLBACK_CRM = {
    "customers": [
        {"customer_id": "CUS-ALPHA", "name": "Alpha Bank", "tier": "Enterprise", "arr": 600000.0, "renewal_date": "2026-12-15", "active": True},
        {"customer_id": "CUS-BETA", "name": "Beta Corp", "tier": "Strategic", "arr": 350000.0, "renewal_date": "2027-01-20", "active": True}
    ]
}

FALLBACK_INCIDENT = {
    "incidents": [
        {"incident_id": "INC-001", "customer_id": "CUS-ALPHA", "title": "SLA Escalation", "priority": "CRITICAL", "status": "OPEN", "created_at": "2026-07-24T12:00:00Z"},
        {"incident_id": "INC-002", "customer_id": "CUS-BETA", "title": "Database Timeout", "priority": "HIGH", "status": "OPEN", "created_at": "2026-07-24T14:30:00Z"}
    ]
}

FALLBACK_WORKFORCE = {
    "specialists": [
        {"specialist_id": "SPEC-001", "name": "Alice Smith", "skills": ["Python", "SQL"], "active": True, "capacity": 3, "current_workload": 1},
        {"specialist_id": "SPEC-002", "name": "Bob Jones", "skills": ["Docker", "FastAPI"], "active": True, "capacity": 4, "current_workload": 2}
    ]
}

FALLBACK_COMMUNICATION = {
    "assignment_requests": []
}

async def execute_tools(state: AgentState) -> dict:
    print("[execute_tools]\nExecuting queries to live microservices...")
    selected_tools = state.get("selected_tools", [])
    run_id = state.get("run_id", "RUN-UNKNOWN")
    
    # Initialize tool client with current run ID correlation header
    client = ToolClient(request_id=run_id)
    
    # Track tasks to call concurrently
    tasks = []
    tool_names = []
    
    for tool_select in selected_tools:
        name = tool_select.get("toolName")
        selected = tool_select.get("selected", False)
        
        if selected:
            tool_names.append(name)
            if name == "crm-service":
                tasks.append(client.get_customers())
            elif name == "incident-service":
                tasks.append(client.get_incidents())
            elif name == "workforce-service":
                tasks.append(client.get_specialists())
            elif name == "communication-service":
                tasks.append(client.get_assignment_requests())
            else:
                # Stub mapping if unknown tool
                tasks.append(asyncio.sleep(0.01, result={}))
                
    tool_results = []
    
    if tasks:
        # Run live queries concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for name, res in zip(tool_names, results):
            if isinstance(res, Exception):
                logger.warning(f"Failed to query {name} live: {str(res)}. Activating offline fallback data.")
                # Load correct fallback dataset
                fallback_data = {}
                if name == "crm-service":
                    fallback_data = FALLBACK_CRM
                elif name == "incident-service":
                    fallback_data = FALLBACK_INCIDENT
                elif name == "workforce-service":
                    fallback_data = FALLBACK_WORKFORCE
                elif name == "communication-service":
                    fallback_data = FALLBACK_COMMUNICATION
                    
                tool_results.append({
                    "tool": name,
                    "status": "FALLBACK",
                    "data": fallback_data,
                    "records_fetched": len(list(fallback_data.values())[0]) if fallback_data else 0
                })
            else:
                # Success
                # Find length of retrieved records
                records_fetched = 0
                if res and isinstance(res, dict):
                    records = list(res.values())[0] if res.values() else []
                    records_fetched = len(records) if isinstance(records, list) else 1
                elif isinstance(res, list):
                    records_fetched = len(res)
                    
                tool_results.append({
                    "tool": name,
                    "status": "SUCCESS",
                    "data": res,
                    "records_fetched": records_fetched
                })
                
    return {"tool_results": tool_results}
