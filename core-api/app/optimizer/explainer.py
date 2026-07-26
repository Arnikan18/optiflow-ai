import logging
from typing import Dict, Any, List
from app.config.settings import settings
from app.goals.providers import get_llm_provider

logger = logging.getLogger("core-api.optimizer.explainer")

def build_explanation_prompt(profile: str, plan: Dict[str, Any], ent_state: Dict[str, Any]) -> str:
    """Builds a structured manager-focused explanation prompt for the LLM."""
    allocations = plan.get("allocations", [])
    metrics = plan.get("metrics", {})
    
    specialists = ent_state.get("specialists", [])
    escalations = ent_state.get("escalations", [])
    customers = ent_state.get("customers", [])
    
    specialist_names = {s.get("specialist_id"): s.get("name") for s in specialists}
    incident_titles = {i.get("incident_id"): i.get("title") for i in escalations}
    
    alloc_narrative = []
    for a in allocations:
        inc_id = a.get("incident_id")
        spec_id = a.get("specialist_id")
        title = incident_titles.get(inc_id, "Unknown incident")
        name = specialist_names.get(spec_id, "Unknown specialist")
        alloc_narrative.append(f"- Assigned incident '{title}' ({inc_id}) to specialist {name} ({spec_id})")
        
    allocations_str = "\n".join(alloc_narrative)
    
    meta = plan.get("metadata", {})
    solver_type = meta.get("solver_type", "Greedy")
    fallback_msg = " (Greedy Fallback Active)" if meta.get("fallback_status") else ""
    
    prompt = f"""
You are the OptiFlow AI scheduling advisor reporting to the Customer Support Manager.
Your task is to write a professional, concise, bulleted natural language justification explaining why this allocation plan was recommended.

PLAN PROFILE: {profile}
SOLVER STRATEGY: {solver_type}{fallback_msg}
ALLOCATIONS IN THIS PLAN:
{allocations_str}

METRICS SUMMARY:
- Match rate: {metrics.get('match_rate', 0.0)}%
- Total assignments: {metrics.get('assigned_count', 0)}
- Unassigned tickets: {metrics.get('unassigned_count', 0)}

INSTRUCTIONS:
1. Explain why this plan profile was generated and why it is preferable.
2. Explain the trade-offs:
   - If "Balanced", highlight that it minimizes fatigue by spreading tasks, but may delay urgent SLA tickets.
   - If "SLA-First", highlight that it prioritizes critical ARR tiers and deadlines, but may overload certain specialists.
3. Keep the justification concise, bulleted, professional, and targeted to the manager. Do not mention internal solver mechanisms or software details.
"""
    return prompt.strip()

def generate_deterministic_fallback_explanation(profile: str, plan: Dict[str, Any], ent_state: Dict[str, Any]) -> str:
    """Generates a stable, repeatable, and deterministic plan explanation when the LLM is unconfigured or fails."""
    metrics = plan.get("metrics", {})
    allocations = plan.get("allocations", [])
    
    assigned_count = metrics.get("assigned_count", 0)
    unassigned_count = metrics.get("unassigned_count", 0)
    
    specialists = ent_state.get("specialists", [])
    escalations = ent_state.get("escalations", [])
    customers = ent_state.get("customers", [])
    
    specialists_used = len(set(a.get("specialist_id") for a in allocations if a.get("specialist_id")))
    meta = plan.get("metadata", {})
    solver_type = meta.get("solver_type", "Greedy")
    
    if profile.lower() == "balanced":
        text = (
            f"### Plan Justification: Balanced Profile\n"
            f"This plan was generated via the {solver_type} strategy to optimize work distribution and prevent team burnout.\n\n"
            f"**Key Allocations:**\n"
            f"- Allocated {assigned_count} active incidents across {specialists_used} specialists matching skill constraints.\n"
            f"- Left {unassigned_count} incidents unassigned due to capacity limits or skill mismatch.\n\n"
            f"**Trade-offs & Preference:**\n"
            f"- **Workload Equality**: Evenly distributes tasks across matching specialists based on relative capacity, minimizing context-switching fatigue.\n"
            f"- **SLA Risk**: May delay high-urgency SLA tickets if specialists with those skills are already loaded."
        )
    else:  # SLA-First
        # Calculate critical items count
        critical_count = sum(1 for e in escalations if str(e.get("priority", "")).upper() in ("CRITICAL", "HIGH"))
        text = (
            f"### Plan Justification: {profile} Profile\n"
            f"This plan was generated via the {solver_type} strategy to prioritize urgent SLA commitments and strategic customer ARR accounts.\n\n"
            f"**Key Allocations:**\n"
            f"- Prioritized {critical_count} critical/high escalations and strategic accounts first.\n"
            f"- Assigned {assigned_count} incidents to specialists matching skill requirements.\n\n"
            f"**Trade-offs & Preference:**\n"
            f"- **SLA Protection**: Ensures that nearest deadlines and high ARR values are resolved first to minimize commercial exposure.\n"
            f"- **Workload Imbalance**: May overload specific specialists who possess highly demanded skills."
        )
    return text

def explain_plan(profile: str, plan: Dict[str, Any], ent_state: Dict[str, Any]) -> str:
    """Computes a plan justification narrative, querying the LLM if available or falling back deterministically."""
    provider_name = settings.llm_provider or "gemini"
    api_key = settings.groq_api_key if provider_name.lower() == "groq" else settings.gemini_api_key
    model = settings.groq_model if provider_name.lower() == "groq" else settings.gemini_model
    
    # 1. Fallback check if LLM configuration is missing
    if not api_key or not model:
        logger.info("LLM config missing. Executing deterministic fallback explanation.")
        return generate_deterministic_fallback_explanation(profile, plan, ent_state)
        
    prompt = build_explanation_prompt(profile, plan, ent_state)
    
    # 2. Try querying the LLM provider
    try:
        provider = get_llm_provider(provider_name, settings)
        explanation = provider.generate_text(prompt, temperature=0.2)
        if explanation and explanation.strip():
            return explanation.strip()
        raise ValueError("Provider returned empty explanation text")
    except Exception as e:
        logger.warning(f"LLM explanation query failed: {str(e)}. Falling back to deterministic narrative.")
        return generate_deterministic_fallback_explanation(profile, plan, ent_state)
