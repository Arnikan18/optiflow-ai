from abc import ABC, abstractmethod
import logging
from typing import List
from pydantic import BaseModel
from google import genai
from google.genai import types
from google.genai.errors import APIError
from groq import Groq

from optiflow_shared.enums import ObjectiveType
from optiflow_shared.tool_contracts import StructuredGoal, TimeHorizon

logger = logging.getLogger("core-api.providers")

class GeminiStructuredGoal(BaseModel):
    summary: str
    objectives: List[str]
    time_horizon_value: int = 7
    time_horizon_unit: str = "DAYS"
    hard_constraints: List[str]
    soft_preferences: List[str]
    requested_actions: List[str]
    ambiguities: List[str]
    unsupported_requests: List[str]

def map_flat_to_structured_goal(gemini_res: GeminiStructuredGoal, model_name: str) -> StructuredGoal:
    objectives = []
    for o in gemini_res.objectives:
        if o in ObjectiveType._value2member_map_:
            objectives.append(ObjectiveType(o))
        elif o.upper() in ObjectiveType.__members__:
            objectives.append(ObjectiveType[o.upper()])
            
    # Ensure time horizon values are valid and greater than 0
    horizon_val = gemini_res.time_horizon_value
    horizon_unit = gemini_res.time_horizon_unit.upper() if gemini_res.time_horizon_unit else "DAYS"
    if horizon_val <= 0:
        horizon_val = 7
        horizon_unit = "DAYS"
        
    return StructuredGoal(
        summary=gemini_res.summary,
        objectives=objectives,
        time_horizon=TimeHorizon(value=horizon_val, unit=horizon_unit),
        hard_constraints=gemini_res.hard_constraints,
        soft_preferences=gemini_res.soft_preferences,
        requested_actions=gemini_res.requested_actions,
        ambiguities=gemini_res.ambiguities,
        unsupported_requests=gemini_res.unsupported_requests,
        interpretation_notes=[f"Parsed via model {model_name}"]
    )

class LLMProvider(ABC):
    @abstractmethod
    def interpret_goal(self, goal_text: str) -> StructuredGoal:
        """Parses raw manager goal text into a StructuredGoal representation."""
        pass

class GeminiLLMProvider(LLMProvider):
    def __init__(self, api_key: str, model_name: str):
        self.api_key = api_key
        self.model_name = model_name

    def interpret_goal(self, goal_text: str) -> StructuredGoal:
        if not self.api_key or not self.model_name:
            raise ValueError("Gemini API key or model name is missing.")
            
        client = genai.Client(api_key=self.api_key)
        
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
        Note that time_horizon_unit must be one of: HOURS, DAYS, WEEKS.
        """
        
        response = client.models.generate_content(
            model=self.model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=GeminiStructuredGoal,
                temperature=0.0
            )
        )
        
        gemini_res = GeminiStructuredGoal.model_validate_json(response.text)
        return map_flat_to_structured_goal(gemini_res, self.model_name)

class GroqLLMProvider(LLMProvider):
    def __init__(self, api_key: str, model_name: str):
        self.api_key = api_key
        self.model_name = model_name

    def interpret_goal(self, goal_text: str) -> StructuredGoal:
        if not self.api_key or not self.model_name:
            raise ValueError("Groq API key or model name is missing.")
            
        client = Groq(api_key=self.api_key)
        
        system_prompt = """
You are the OptiFlow AI goal interpreter. Your task is to translate a natural language manager goal into a StructuredGoal JSON object.
Generate a JSON object conforming strictly to the requested schema.
You MUST output ONLY a valid JSON object. No extra explanations, comments, or surrounding text outside of JSON.
        """
        
        user_prompt = f"""
Identify target business objectives from:
- SLA_PROTECTION (sla, commitments, breach)
- RENEWAL_PROTECTION (renewals, renewal exposure)
- COMMERCIAL_PROTECTION (arr, commercial, revenue)
- CUSTOMER_FAIRNESS (fairness, balance)
- WORKLOAD_PROTECTION (workload, capacity, overload)
- MINIMISE_CONTEXT_SWITCHING (context switching, fatigue)

Goal text: "{goal_text}"

You must output a JSON object with this exact structure:
{{
  "summary": "String summarizing the goal",
  "objectives": ["Array of ObjectiveType strings"],
  "time_horizon_value": 7,
  "time_horizon_unit": "DAYS",
  "hard_constraints": ["Array of strings"],
  "soft_preferences": ["Array of strings"],
  "requested_actions": ["Array of strings"],
  "ambiguities": ["Array of strings"],
  "unsupported_requests": ["Array of strings"]
}}
"""
        
        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            model=self.model_name,
            response_format={"type": "json_object"},
            temperature=0.0
        )
        
        raw_content = chat_completion.choices[0].message.content
        gemini_res = GeminiStructuredGoal.model_validate_json(raw_content)
        return map_flat_to_structured_goal(gemini_res, self.model_name)

def get_llm_provider(provider_name: str, settings) -> LLMProvider:
    provider_name_lower = provider_name.strip().lower()
    if provider_name_lower == "groq":
        return GroqLLMProvider(api_key=settings.groq_api_key, model_name=settings.groq_model)
    else:
        # Default to Gemini
        return GeminiLLMProvider(api_key=settings.gemini_api_key, model_name=settings.gemini_model)
