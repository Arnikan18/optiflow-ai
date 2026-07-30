import logging
from typing import Dict, Any
from app.agent.state import AgentState
from app.services.decision_intelligence import DecisionIntelligenceService
from app.services.decision_presentation import DecisionPresentationService

logger = logging.getLogger("core-api.nodes.decision_intelligence")

async def decision_intelligence(state: AgentState) -> dict:
    """Graph node that enriches AgentState with structured decision intelligence.
    
    Acts as a passive explanation layer. If any exception occurs, it is caught
    and logged so that execution of the run is not blocked.
    """
    logger.info("[decision_intelligence] Node execution started.")
    
    explanation = None
    explanation_dict = None
    history = list(state.get("decision_history") or [])
    
    # 1. Generate canonical DTO explanation
    try:
        explanation = DecisionIntelligenceService.build_explanation(state)
        explanation_dict = explanation.model_dump(mode="json")
        
        # Immutable append: write deep copy serialized snapshot to decision history
        history.append(explanation_dict)
        logger.info(f"[decision_intelligence] Generated explanation DTO ID: {explanation.metadata.decision_id}")
    except Exception as e:
        logger.exception(f"[decision_intelligence] Failed to generate canonical decision explanation: {e}")
        # Return state unchanged to ensure passive explainability layer safety
        return {"decision_explanation": None}

    # 2. Translate DTO explanation to Presentation summaries (Business & Change)
    business_summary = None
    change_summary = None
    try:
        if explanation:
            presentation = DecisionPresentationService.generate_presentation(explanation)
            business_summary = presentation.business_summary
            change_summary = presentation.change_summary
            logger.info("[decision_intelligence] Successfully rendered Presentation summaries.")
    except Exception as e:
        logger.exception(f"[decision_intelligence] Failed to generate presentation views: {e}")
        # Do not block execution: leave summaries as None and proceed

    return {
        "decision_explanation": explanation_dict,
        "decision_history": history,
        "business_summary": business_summary,
        "change_summary": change_summary
    }
