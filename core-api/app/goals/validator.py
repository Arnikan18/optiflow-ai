"""Goal Validator module.

Responsible for checking the structural and semantic validity of the parsed StructuredGoal
and mapping it to a GoalValidationResult indicating if the goal is valid, ambiguous, or blocked.

Intended Usage:
    Invoked within the `validate_goal` node of the LangGraph flow to block or pause the run.
"""

from optiflow_shared.tool_contracts import StructuredGoal, GoalValidationResult

def validate_goal(goal: StructuredGoal) -> GoalValidationResult:
    """Validates the properties of a StructuredGoal.
    
    Verifies that the goal is non-empty, contains supported objectives, has a positive
    time horizon, and consolidates any duplicate objectives or flags ambiguities.
    
    Args:
        goal: The structured goal to validate.
        
    Returns:
        GoalValidationResult indicating validation status and blocker logs.
    """
    valid = True
    clarification_required = False
    blocking_reasons = []
    warnings = []
    
    # 1. Empty goal check
    if not goal.summary.strip():
        valid = False
        blocking_reasons.append("Goal summary cannot be empty.")
        return GoalValidationResult(
            valid=valid,
            clarification_required=clarification_required,
            blocking_reasons=blocking_reasons,
            warnings=warnings
        )
        
    # 2. Too long check (limit to 500 chars for demo safety)
    if len(goal.summary) > 500:
        valid = False
        blocking_reasons.append("Goal length exceeds maximum limit of 500 characters.")
        
    # 3. Time horizon validation
    if goal.time_horizon.value <= 0:
        valid = False
        blocking_reasons.append("Time horizon value must be greater than zero.")
        
    # 4. Duplicate objectives check
    if len(goal.objectives) != len(set(goal.objectives)):
        warnings.append("Duplicate objectives detected and consolidated.")
        goal.objectives = list(dict.fromkeys(goal.objectives))

    # 5. Unsupported objectives check
    if not goal.objectives:
        valid = False
        blocking_reasons.append("No supported business objectives could be interpreted from the goal text.")

    # 6. Ambiguity check (triggers clarification request)
    if goal.ambiguities:
        clarification_required = True
        
    return GoalValidationResult(
        valid=valid and not blocking_reasons,
        clarification_required=clarification_required,
        blocking_reasons=blocking_reasons,
        warnings=warnings,
        clarification_question=goal.ambiguities[0] if goal.ambiguities else None
    )
