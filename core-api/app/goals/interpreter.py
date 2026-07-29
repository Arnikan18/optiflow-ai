"""Goal Interpreter module.

Responsible for parsing the manager's natural language goal input
and mapping it to a StructuredGoal representation using Gemini API structured outputs,
falling back gracefully to a deterministic rule-based engine on key failure modes.
"""

import logging
import re
from typing import List
from optiflow_shared.enums import ObjectiveType
from optiflow_shared.tool_contracts import StructuredGoal, TimeHorizon
from app.llm_settings.service import RuntimeLLMSettings, llm_settings_service

logger = logging.getLogger("core-api.interpreter")


def interpret_goal_text_fallback(goal_text: str, notes: List[str]) -> StructuredGoal:
    """Fallback rule-based goal interpreter used when Gemini is unavailable or not configured."""
    normalized = goal_text.lower()
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

    hard_constraints = [
        "REQUIRED_SKILL_MATCH",
        "CONFIRMED_AVAILABILITY",
        "MAXIMUM_CAPACITY"
    ]
    
    soft_preferences = []
    if ObjectiveType.CUSTOMER_FAIRNESS in objectives:
        soft_preferences.append("AVOID_REPEATED_POSTPONEMENT")
    if ObjectiveType.MINIMISE_CONTEXT_SWITCHING in objectives:
        soft_preferences.append("REDUCE_CONTEXT_SWITCHING")
    else:
        soft_preferences.append("MINIMISE_CONTEXT_SWITCHING")

    requested_actions = ["GENERATE_ALLOCATION_PLAN"]
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
        interpretation_notes=notes
    )


from pydantic import BaseModel

from app.goals.providers import get_llm_provider


def interpret_goal_text(
    goal_text: str,
    runtime_settings: RuntimeLLMSettings | None = None,
    provider_name: str | None = None,
    model_name: str | None = None,
) -> StructuredGoal:
    """Parses goal text into a StructuredGoal.
    
    Attempts to call the configured LLM provider (Gemini or Groq) using a structured JSON schema,
    falling back gracefully to a deterministic rule-based parser on any failures.
    """
    if not goal_text or not goal_text.strip():
        return StructuredGoal(
            summary="",
            objectives=[],
            time_horizon=TimeHorizon(value=7, unit="DAYS"),
            hard_constraints=[],
            soft_preferences=[],
            requested_actions=[],
            ambiguities=[],
            unsupported_requests=[],
            interpretation_notes=["Empty goal text input"]
        )

    runtime = runtime_settings or llm_settings_service.current()
    selected = runtime.provider_for(provider_name, model_name)
    if selected is None:
        logger.info(
            "AI-assisted goal interpretation is not configured. "
            "Falling back to rule-based interpreter."
        )
        notes = ["LIMITED_CAPABILITY_MODE", "Fallback rule-based interpreter applied due to missing config"]
        return interpret_goal_text_fallback(goal_text, notes)

    selected_name, provider_settings = selected
    try:
        provider = get_llm_provider(
            selected_name,
            model_name=provider_settings.model_name,
            api_keys=[item.api_key for item in provider_settings.credentials],
        )
        return provider.interpret_goal(goal_text)
    except Exception as e:
        logger.warning(
            "%s interpretation failed. Executing rule-based fallback.",
            selected_name,
        )
        notes = [
            "LIMITED_CAPABILITY_MODE",
            f"Fallback applied because {selected_name} was unavailable",
        ]
        return interpret_goal_text_fallback(goal_text, notes)
