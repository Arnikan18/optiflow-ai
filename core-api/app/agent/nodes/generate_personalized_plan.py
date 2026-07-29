import logging
from app.agent.state import AgentState
from app.database.session import async_session
from app.services.manager_preference_service import ManagerPreferenceService
from app.services.recommendation_engine import RecommendationEngine
from app.services.explanation_engine import ExplanationEngine

logger = logging.getLogger("core-api.nodes.generate_personalized_plan")

async def generate_personalized_plan(state: AgentState) -> dict:
    """Graph node that computes the Personalized Recommendation from the generated candidates.
    
    Loads preference memory, delegates ranking to RecommendationEngine, explains results
    using ExplanationEngine, and attaches the resulting reference to the AgentState.
    """
    run_id = state.get("run_id", "unknown")
    candidate_plans = state.get("candidate_plans") or []
    goal_text = state.get("goal_text")
    
    print(f"[generate_personalized_plan] Running for run {run_id}. Candidates: {len(candidate_plans)}")
    
    if not candidate_plans:
        logger.warning(f"[generate_personalized_plan] No candidate plans found in state for run {run_id}.")
        return {
            "personalized_recommendation": None
        }
        
    try:
        async with async_session() as session:
            async with session.begin():
                # 1. Load preference memory from database
                memory = await ManagerPreferenceService.load_memory(session)
                
        # 2. Invoke RecommendationEngine to rank candidates
        result = RecommendationEngine.rank_candidates(
            candidate_plans=candidate_plans,
            memory=memory,
            goal_text=goal_text
        )
        
        # 3. Invoke ExplanationEngine to produce detailed templates and mapping
        explained_result = ExplanationEngine.explain_recommendation(
            result=result,
            memory=memory,
            candidate_plans=candidate_plans
        )
        
        # 4. Serialize Pydantic model (including enums) to standard dict for AgentState compatibility
        personalized_rec = explained_result.model_dump(mode="json")
        
        # Keep profile name at the root for easier UI indexing
        best_plan = candidate_plans[result.candidate_index]
        personalized_rec["profile"] = best_plan.get("profile")
        
        logger.info(
            f"[generate_personalized_plan] Recommendation: {result.candidate_plan_id} "
            f"(profile: {best_plan.get('profile')}), level: {explained_result.confidence_level}, "
            f"state: {explained_result.learning_state}, reason: {explained_result.reason}"
        )
        
        return {
            "personalized_recommendation": personalized_rec
        }
        
    except Exception as e:
        logger.error(f"[generate_personalized_plan] Error generating personalization recommendation for {run_id}: {str(e)}")
        # Failure policy: Graceful degradation, continue workflow normally with None recommendation
        return {
            "personalized_recommendation": None
        }
