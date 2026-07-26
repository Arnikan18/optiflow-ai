import logging
from typing import Dict, Any, List
from app.optimizer.base import BaseOptimizer

logger = logging.getLogger("core-api.optimizer.greedy")

class GreedyOptimizer(BaseOptimizer):
    """Greedy priority constraint matching optimizer strategy."""

    def generate_plans(
        self,
        customers: List[Dict[str, Any]],
        escalations: List[Dict[str, Any]],
        specialists: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        # Import resolving helpers directly from app.optimizer.solver to avoid circular loops
        from app.optimizer.solver import score_incident_priority, resolve_required_skills

        customers_map = {c.get("customer_id"): c for c in customers if c.get("customer_id")}
        
        # Filter active incidents
        open_incidents = [
            inc for inc in escalations 
            if str(inc.get("status", "")).upper() in ("OPEN", "UNASSIGNED", "ASSIGNED")
        ]
        
        # 1. PLAN: Balanced
        specs_balanced = []
        for spec in specialists:
            sid = spec.get("specialist_id")
            if sid:
                specs_balanced.append({
                    "specialist_id": sid,
                    "name": spec.get("name"),
                    "skills": [s.lower() for s in spec.get("skills", [])],
                    "capacity": int(spec.get("capacity")) if spec.get("capacity") is not None else 3,
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
                if req_skills:
                    has_skill = any(s in spec["skills"] for s in req_skills)
                    if not has_skill:
                        continue
                if spec["workload"] >= spec["capacity"]:
                    continue
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
                
        total_incidents = len(open_incidents)
        assigned_count = len(balanced_allocations)
        match_rate = (assigned_count / total_incidents * 100.0) if total_incidents > 0 else 100.0
        
        from app.optimizer.profiles import get_profile_description
        balanced_plan = {
            "plan_id": "PLAN-BALANCED",
            "profile": "Balanced",
            "description": get_profile_description("Balanced"),
            "objective_value": round(match_rate * 0.9, 1),
            "allocations": balanced_allocations,
            "unassigned_incidents": balanced_unassigned,
            "metrics": {
                "match_rate": match_rate,
                "unassigned_count": len(balanced_unassigned),
                "assigned_count": assigned_count
            },
            "metadata": {
                "solver_type": "Greedy",
                "fallback_status": False,
                "feasibility": True
            }
        }
        
        # 2. PLAN: SLA-First
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
                    "capacity": int(spec.get("capacity")) if spec.get("capacity") is not None else 3,
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
                if req_skills:
                    has_skill = any(s in spec["skills"] for s in req_skills)
                    if not has_skill:
                        continue
                if spec["workload"] >= spec["capacity"]:
                    continue
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
            "description": get_profile_description("SLA-First"),
            "objective_value": round(match_rate_sla, 1),
            "allocations": sla_allocations,
            "unassigned_incidents": sla_unassigned,
            "metrics": {
                "match_rate": match_rate_sla,
                "unassigned_count": len(sla_unassigned),
                "assigned_count": assigned_count_sla
            },
            "metadata": {
                "solver_type": "Greedy",
                "fallback_status": False,
                "feasibility": True
            }
        }
        
        return [balanced_plan, sla_plan]
