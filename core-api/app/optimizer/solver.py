import logging
from typing import Dict, Any, List

logger = logging.getLogger("core-api.optimizer.solver")

def score_incident_priority(incident: Dict[str, Any], customers_map: Dict[str, Dict[str, Any]]) -> float:
    """Calculates SLA and customer value scores to rank critical incidents."""
    priority = incident.get("priority", "LOW").upper()
    
    # Priority scoring weights
    priority_weights = {
        "CRITICAL": 100.0,
        "HIGH": 50.0,
        "MEDIUM": 20.0,
        "LOW": 5.0
    }
    score = priority_weights.get(priority, 5.0)
    
    # Customer value ARR weight
    customer_id = incident.get("customer_id")
    customer = customers_map.get(customer_id)
    if customer:
        arr = float(customer.get("arr") or 0.0)
        # Normalize ARR: add 1.0 weight point per $100K ARR
        score += arr / 100000.0
        
    return score

def resolve_required_skills(incident: Dict[str, Any]) -> List[str]:
    """Resolves required skills of an incident using payload details or title keywords."""
    # Check if raw skills are returned in payload
    skills = incident.get("skills")
    if isinstance(skills, list):
        return [str(s).lower() for s in skills]
        
    title = str(incident.get("title", "")).lower()
    description = str(incident.get("description", "")).lower()
    text = f"{title} {description}"
    
    required = []
    # Keyword parsing
    if "integration" in text or "api" in text or "webhook" in text:
        required.append("integration")
    if "security" in text or "auth" in text or "login" in text or "token" in text:
        required.append("security")
    if "database" in text or "sql" in text or "query" in text or "timeout" in text:
        required.append("database")
    if "billing" in text or "subscription" in text or "invoice" in text or "payment" in text:
        required.append("billing")
        
    return required

def generate_optimization_plans(
    customers: List[Dict[str, Any]],
    escalations: List[Dict[str, Any]],
    specialists: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Gateway entry point that delegates to the configured Strategy via the Factory with transparent greedy fallback."""
    from app.optimizer.factory import OptimizerFactory
    from app.optimizer.greedy import GreedyOptimizer
    from app.config.settings import settings
    
    strategy = settings.optimization_strategy or "greedy"
    try:
        optimizer = OptimizerFactory.get_optimizer(strategy)
        plans = optimizer.generate_plans(customers, escalations, specialists)
        return plans
    except Exception as e:
        logger.warning(f"Optimization execution failed under strategy '{strategy}': {str(e)}. Falling back to GreedyOptimizer.")
        # Run greedy optimizer fallback
        greedy = GreedyOptimizer()
        plans = greedy.generate_plans(customers, escalations, specialists)
        for plan in plans:
            if "metadata" not in plan:
                plan["metadata"] = {}
            plan["metadata"]["fallback_status"] = True
            plan["metadata"]["solver_type"] = "Greedy (Fallback)"
        return plans
