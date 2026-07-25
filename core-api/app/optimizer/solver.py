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
    """Generates two scheduling plans: Balanced (minimize fatigue) and SLA-First."""
    customers_map = {c.get("customer_id"): c for c in customers if c.get("customer_id")}
    
    # Filter open/active incidents
    open_incidents = [
        inc for inc in escalations 
        if str(inc.get("status", "")).upper() in ("OPEN", "UNASSIGNED", "ASSIGNED")
    ]
    
    # 1. PLAN: Balanced
    # Goal: Distribute work evenly across matching specialists.
    # We copy the workloads to track state changes
    specs_balanced = []
    for spec in specialists:
        sid = spec.get("specialist_id")
        if sid:
            specs_balanced.append({
                "specialist_id": sid,
                "name": spec.get("name"),
                "skills": [s.lower() for s in spec.get("skills", [])],
                "capacity": int(spec.get("capacity") or 3),
                "workload": int(spec.get("current_workload") or 0)
            })
            
    balanced_allocations = []
    balanced_unassigned = []
    
    for inc in open_incidents:
        inc_id = inc.get("incident_id")
        req_skills = resolve_required_skills(inc)
        
        best_spec = None
        best_ratio = 999.0
        
        for spec in specs_balanced:
            # Skill check
            if req_skills:
                has_skill = any(s in spec["skills"] for s in req_skills)
                if not has_skill:
                    continue
                    
            # Capacity check
            if spec["workload"] >= spec["capacity"]:
                continue
                
            # Ratio score: workload / capacity
            ratio = float(spec["workload"]) / float(spec["capacity"])
            if ratio < best_ratio:
                best_ratio = ratio
                best_spec = spec
                
        if best_spec:
            best_spec["workload"] += 1
            balanced_allocations.append({
                "incident_id": inc_id,
                "specialist_id": best_spec["specialist_id"],
                "matched_skills": list(set(req_skills) & set(best_spec["skills"]))
            })
        else:
            balanced_unassigned.append(inc_id)
            
    # Score metrics
    total_incidents = len(open_incidents)
    assigned_count = len(balanced_allocations)
    match_rate = (assigned_count / total_incidents * 100.0) if total_incidents > 0 else 100.0
    
    balanced_plan = {
        "plan_id": "PLAN-BALANCED",
        "profile": "Balanced",
        "objective_value": round(match_rate * 0.9, 1),
        "allocations": balanced_allocations,
        "unassigned_incidents": balanced_unassigned,
        "metrics": {
            "match_rate": match_rate,
            "unassigned_count": len(balanced_unassigned),
            "assigned_count": assigned_count
        }
    }
    
    # 2. PLAN: SLA-First
    # Goal: Prioritize critical SLA alerts first.
    scored_incidents = []
    for inc in open_incidents:
        score = score_incident_priority(inc, customers_map)
        scored_incidents.append((score, inc))
    scored_incidents.sort(key=lambda x: x[0], reverse=True)
    
    specs_sla = []
    for spec in specialists:
        sid = spec.get("specialist_id")
        if sid:
            specs_sla.append({
                "specialist_id": sid,
                "name": spec.get("name"),
                "skills": [s.lower() for s in spec.get("skills", [])],
                "capacity": int(spec.get("capacity") or 3),
                "workload": int(spec.get("current_workload") or 0)
            })
            
    sla_allocations = []
    sla_unassigned = []
    
    for score, inc in scored_incidents:
        inc_id = inc.get("incident_id")
        req_skills = resolve_required_skills(inc)
        
        best_spec = None
        best_margin = -1
        
        for spec in specs_sla:
            # Skill check
            if req_skills:
                has_skill = any(s in spec["skills"] for s in req_skills)
                if not has_skill:
                    continue
                    
            # Capacity check
            if spec["workload"] >= spec["capacity"]:
                continue
                
            # SLA strategy: prioritize specialists with highest available capacity margin
            margin = spec["capacity"] - spec["workload"]
            if margin > best_margin:
                best_margin = margin
                best_spec = spec
                
        if best_spec:
            best_spec["workload"] += 1
            sla_allocations.append({
                "incident_id": inc_id,
                "specialist_id": best_spec["specialist_id"],
                "matched_skills": list(set(req_skills) & set(best_spec["skills"]))
            })
        else:
            sla_unassigned.append(inc_id)
            
    assigned_count_sla = len(sla_allocations)
    match_rate_sla = (assigned_count_sla / total_incidents * 100.0) if total_incidents > 0 else 100.0
    
    sla_plan = {
        "plan_id": "PLAN-SLA",
        "profile": "SLA-First",
        "objective_value": round(match_rate_sla, 1),
        "allocations": sla_allocations,
        "unassigned_incidents": sla_unassigned,
        "metrics": {
            "match_rate": match_rate_sla,
            "unassigned_count": len(sla_unassigned),
            "assigned_count": assigned_count_sla
        }
    }
    
    return [balanced_plan, sla_plan]
