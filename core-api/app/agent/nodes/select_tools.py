from app.agent.state import AgentState
from app.evidence.registry import EvidenceRegistry
from optiflow_shared.enums import EvidenceType, ToolService

async def select_tools(state: AgentState) -> dict:
    """Agent node responsible for selecting/skipping mock services.
    
    Inspects required evidence types, looks up service ownership, and determines
    which tool-services must be invoked in the next phase.
    """
    print("[select_tools]\nTools selected")
    
    reqs_list = state.get("evidence_requirements", [])
    required_evidence_types = {r["evidence_type"] for r in reqs_list}
    
    registry = EvidenceRegistry()
    
    # Tool services to select (typed enums)
    services = [ToolService.CRM, ToolService.INCIDENT, ToolService.WORKFORCE, ToolService.COMMUNICATION]
    selected_tools = []
    
    # Determine which tools are active based on the required evidence mapping
    for srv in services:
        needed_evidence = []
        for et_str in required_evidence_types:
            try:
                et = EvidenceType(et_str)
                auth_srv = registry.get_authoritative_tool(et)
                if auth_srv == srv:
                    needed_evidence.append(et_str)
            except ValueError:
                pass
                
        if needed_evidence:
            selected_tools.append({
                "toolName": srv.value,
                "selected": True,
                "reason": f"Required evidence categories: {', '.join(needed_evidence)}",
                "requestedEvidence": needed_evidence
            })
        else:
            selected_tools.append({
                "toolName": srv.value,
                "selected": False,
                "reason": "Commercial or notification evidence is not required for this goal.",
                "requestedEvidence": []
            })
            
    return {"selected_tools": selected_tools}
