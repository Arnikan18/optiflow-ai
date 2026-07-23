from app.agent.state import AgentState
from app.evidence.planner import build_evidence_requirements
from optiflow_shared.tool_contracts import StructuredGoal

async def plan_evidence(state: AgentState) -> dict:
    print("[plan_evidence]\nEvidence requirement planned")
    sg_dict = state.get("structured_goal")
    if not sg_dict:
        return {"evidence_requirements": []}
        
    sg = StructuredGoal(**sg_dict)
    reqs = build_evidence_requirements(sg)
    
    # Store requirements as list of dicts in state
    return {"evidence_requirements": [r.model_dump() for r in reqs]}
