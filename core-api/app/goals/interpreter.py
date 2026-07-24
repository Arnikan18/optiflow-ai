"""Goal Interpreter module.

Responsible for parsing the manager's natural language goal input
and mapping it to a StructuredGoal representation containing objectives,
constraints, preferences, and parsed time horizons.

Intended Usage:
    Invoked within the `interpret_goal` node of the LangGraph flow.

Extension Points:
    - In future sets, this rule-based parsing can be replaced or enhanced with LLM calls.
"""

from optiflow_shared.enums import ObjectiveType
from optiflow_shared.tool_contracts import StructuredGoal, TimeHorizon
import re

def interpret_goal_text(goal_text: str) -> StructuredGoal:
    """Parses a natural-language goal string into a StructuredGoal.
    
    Uses keyword matching to identify objectives, extract duration windows,
    and detect potential strategic ambiguities.
    
    Args:
        goal_text: The user-supplied goal text.
        
    Returns:
        StructuredGoal containing objectives, constraints, and parsed time horizon.
    """
    normalized = goal_text.lower()
    
    # 1. Parse objectives
    objectives = []
    if "sla" in normalized or "breach" in normalized or "commitments" in normalized:
        objectives.append(ObjectiveType.SLA_PROTECTION)
    if "renew" in normalized or "renewal" in normalized:
        objectives.append(ObjectiveType.RENEWAL_PROTECTION)
        if ObjectiveType.SLA_PROTECTION not in objectives:
            objectives.append(ObjectiveType.SLA_PROTECTION)
        objectives.append(ObjectiveType.COMMERCIAL_PROTECTION)
    if "commercial" in normalized or "arr" in normalized or "revenue" in normalized:
        if ObjectiveType.COMMERCIAL_PROTECTION not in objectives:
            objectives.append(ObjectiveType.COMMERCIAL_PROTECTION)
    if "fair" in normalized or "postpone" in normalized:
        objectives.append(ObjectiveType.CUSTOMER_FAIRNESS)
    if "workload" in normalized or "overload" in normalized or "fatigue" in normalized:
        objectives.append(ObjectiveType.WORKLOAD_PROTECTION)
    if "context" in normalized or "switch" in normalized:
        objectives.append(ObjectiveType.MINIMISE_CONTEXT_SWITCHING)
        
    if not objectives and goal_text.strip():
        objectives.append(ObjectiveType.SLA_PROTECTION)

    # 2. Parse time horizon
    horizon_val = 7
    horizon_unit = "DAYS"
    
    if "four hours" in normalized or "4 hours" in normalized:
        horizon_val = 4
        horizon_unit = "HOURS"
    elif "hour" in normalized:
        match = re.search(r"(\d+)\s*hour", normalized)
        if match:
            horizon_val = int(match.group(1))
            horizon_unit = "HOURS"
    elif "day" in normalized:
        match = re.search(r"(\d+)\s*day", normalized)
        if match:
            horizon_val = int(match.group(1))
            horizon_unit = "DAYS"

    # 3. Hard constraints
    hard_constraints = [
        "REQUIRED_SKILL_MATCH",
        "CONFIRMED_AVAILABILITY",
        "MAXIMUM_CAPACITY"
    ]
    
    # 4. Soft preferences
    soft_preferences = []
    if ObjectiveType.CUSTOMER_FAIRNESS in objectives:
        soft_preferences.append("AVOID_REPEATED_POSTPONEMENT")
    if ObjectiveType.MINIMISE_CONTEXT_SWITCHING in objectives:
        soft_preferences.append("REDUCE_CONTEXT_SWITCHING")
    else:
        soft_preferences.append("MINIMISE_CONTEXT_SWITCHING")

    # 5. Requested actions
    requested_actions = ["GENERATE_ALLOCATION_PLAN"]

    # 6. Detect ambiguity
    ambiguities = []
    if "important" in normalized:
        ambiguities.append("Should customer importance primarily mean nearest SLA deadline, renewal exposure or strategic account tier?")

    return StructuredGoal(
        summary=goal_text.strip(),
        objectives=objectives,
        time_horizon=TimeHorizon(value=horizon_val, unit=horizon_unit),
        hard_constraints=hard_constraints,
        soft_preferences=soft_preferences,
        requested_actions=requested_actions,
        ambiguities=ambiguities,
        unsupported_requests=[],
        interpretation_notes=[]
    )
