from app.agent.state import AgentState
from app.goals.validator import validate_goal as run_validator
from optiflow_shared.tool_contracts import StructuredGoal

async def validate_goal(state: AgentState) -> dict:
    print("[validate_goal]\nGoal validated")
    sg_dict = state.get("structured_goal")
    if not sg_dict:
        sg = StructuredGoal(
            summary="",
            objectives=[],
            time_horizon={"value": 7, "unit": "DAYS"},
            hard_constraints=[],
            soft_preferences=[],
            requested_actions=[],
            ambiguities=[],
            unsupported_requests=[],
            interpretation_notes=[]
        )
    else:
        sg = StructuredGoal(**sg_dict)
        
    validation_res = run_validator(sg)
    
    # Simple state transition flags for minimal state
    status_val = "PLANNING"
    if not validation_res.valid:
        status_val = "FAILED_SAFE"
    elif validation_res.clarification_required and not state.get("clarification_resolved"):
        status_val = "NEEDS_CLARIFICATION"
        
    return {
        "status": status_val
    }
