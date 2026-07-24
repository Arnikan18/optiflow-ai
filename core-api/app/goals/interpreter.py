"""Goal Interpreter module.

Responsible for parsing the manager's natural language goal input
and mapping it to a StructuredGoal representation using Gemini API structured outputs,
falling back gracefully to a deterministic rule-based engine on key failure modes.
"""

import logging
import re
from typing import List
from google import genai
from google.genai import types
from google.genai.errors import APIError

from optiflow_shared.enums import ObjectiveType
from optiflow_shared.tool_contracts import StructuredGoal, TimeHorizon
from app.config.settings import settings

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


def interpret_goal_text(goal_text: str) -> StructuredGoal:
    """Parses goal text into a StructuredGoal.
    
    Attempts to call Gemini using the google-genai Pydantic response schema,
    falling back to a rule-based parser on timeouts, exceptions, or missing API keys.
    """
    if not settings.gemini_api_key or not settings.gemini_model:
        logger.info("Gemini API key or model is not configured. Falling back to rule-based interpreter.")
        notes = ["LIMITED_CAPABILITY_MODE", "Fallback rule-based interpreter applied due to missing config"]
        return interpret_goal_text_fallback(goal_text, notes)

    try:
        # Initializing Gemini Client
        client = genai.Client(api_key=settings.gemini_api_key)
        
        prompt = f"""
        You are the OptiFlow AI goal interpreter. Your task is to translate a natural language manager goal into a StructuredGoal JSON object.
        Identify target business objectives:
        - SLA_PROTECTION (sla, commitments, breach)
        - RENEWAL_PROTECTION (renewals, renewal exposure)
        - COMMERCIAL_PROTECTION (arr, commercial, revenue)
        - CUSTOMER_FAIRNESS (fairness, balance)
        - WORKLOAD_PROTECTION (workload, capacity, overload)
        - MINIMISE_CONTEXT_SWITCHING (context switching, fatigue)
        
        Analyze the manager goal text: "{goal_text}"
        Generate a StructuredGoal structure conforming strictly to the requested schema.
        """
        
        response = client.models.generate_content(
            model=settings.gemini_model,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=StructuredGoal,
                temperature=0.0
            )
        )
        
        # Parse Pydantic model directly from response
        # Google-genai parses and validates the Pydantic schema in background
        structured_goal = StructuredGoal.model_validate_json(response.text)
        structured_goal.interpretation_notes.append(f"Parsed via Gemini model {settings.gemini_model}")
        return structured_goal

    except (APIError, Exception) as e:
        logger.warning(f"Gemini interpretation failed: {str(e)}. Executing rule-based fallback.")
        notes = ["LIMITED_CAPABILITY_MODE", f"Fallback applied due to Gemini API failure: {str(e)}"]
        return interpret_goal_text_fallback(goal_text, notes)
