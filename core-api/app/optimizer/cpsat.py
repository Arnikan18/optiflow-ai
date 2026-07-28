import logging
import time
from typing import Dict, Any, List
from ortools.sat.python import cp_model
from app.optimizer.base import BaseOptimizer
from app.config.settings import settings

logger = logging.getLogger("core-api.optimizer.cpsat")

class CPSatOptimizer(BaseOptimizer):
    """Google OR-Tools CP-SAT portfolio-level scheduling optimizer strategy."""

    def generate_plans(
        self,
        customers: List[Dict[str, Any]],
        escalations: List[Dict[str, Any]],
        specialists: List[Dict[str, Any]],
        excluded_pairs: List[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Generates candidate optimization plans using CP-SAT portfolios.
        
        excluded_pairs: list of {"specialist_id": str, "incident_id": str} dicts
        representing specialist-incident assignments that must not be made
        (e.g. a specialist previously rejected the incident).
        """
        from app.optimizer.profiles import DEFAULT_PROFILES, get_profile_weights
        
        excluded_pairs = excluded_pairs or []
        plans = []
        for profile_name in DEFAULT_PROFILES.keys():
            weights = get_profile_weights(profile_name)
            plan = self._solve_portfolio(profile_name, weights, customers, escalations, specialists, excluded_pairs)
            plans.append(plan)
            
        return plans

    def _solve_portfolio(
        self,
        profile_name: str,
        weights: Dict[str, int],
        customers: List[Dict[str, Any]],
        escalations: List[Dict[str, Any]],
        specialists: List[Dict[str, Any]],
        excluded_pairs: List[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Formulates and solves the portfolio allocation problem under a specific profile's weights."""
        from app.optimizer.solver import score_incident_priority, resolve_required_skills
        
        excluded_pairs = excluded_pairs or []
        # Build a fast lookup set: {(inc_id, spec_id), ...}
        excluded_set = {
            (ep["incident_id"], ep["specialist_id"])
            for ep in excluded_pairs
            if ep.get("incident_id") and ep.get("specialist_id")
        }
        
        # 1. Initialize CP-SAT Model
        start_time = time.perf_counter()
        model = cp_model.CpModel()

        
        # Filter active incidents
        open_incidents = [
            inc for inc in escalations 
            if str(inc.get("status", "")).upper() in ("OPEN", "UNASSIGNED", "ASSIGNED")
        ]
        
        customers_map = {c.get("customer_id"): c for c in customers if c.get("customer_id")}
        
        # Helper variables
        x = {}  # (inc_id, spec_id) -> decision variable
        u = {}  # inc_id -> unassigned variable
        
        # 2. Decision Variables
        # - x[i, j] = 1 if incident i is assigned to specialist j, else 0
        # - u[i] = 1 if incident i is unassigned, else 0
        for inc in open_incidents:
            inc_id = inc.get("incident_id")
            u[inc_id] = model.NewBoolVar(f"unassigned_{inc_id}")
            
            for spec in specialists:
                spec_id = spec.get("specialist_id")
                x[(inc_id, spec_id)] = model.NewBoolVar(f"assign_{inc_id}_{spec_id}")
                
        # 3. Hard Constraints
        # Constraint A: Every escalation must either be assigned to exactly one engineer, or be unassigned.
        # Formulation: u[i] + sum(x[i, j] for j in J) == 1
        for inc in open_incidents:
            inc_id = inc.get("incident_id")
            model.Add(u[inc_id] + sum(x[(inc_id, s.get("specialist_id"))] for s in specialists) == 1)
            
        # Constraint B: Engineer capacity must never be exceeded.
        # Formulation: current_workload_j + sum(x[i, j] for i in I) <= capacity_j
        for spec in specialists:
            spec_id = spec.get("specialist_id")
            cap_val = spec.get("capacity")
            capacity = int(cap_val) if cap_val is not None else 3
            current_workload = int(spec.get("current_workload") or 0)
            
            model.Add(
                current_workload + sum(x[(inc.get("incident_id"), spec_id)] for inc in open_incidents) <= capacity
            )
            
        # Constraint C: Skill check matching rules.
        # Formulation: if spec lacks matching skills, x[i, j] == 0
        for inc in open_incidents:
            inc_id = inc.get("incident_id")
            req_skills = resolve_required_skills(inc)
            
            for spec in specialists:
                spec_id = spec.get("specialist_id")
                spec_skills = [sk.lower() for sk in spec.get("skills", [])]
                
                if req_skills:
                    has_skill = any(sk in spec_skills for sk in req_skills)
                    if not has_skill:
                        # Enforce no assignment
                        model.Add(x[(inc_id, spec_id)] == 0)

        # Constraint D: Exclusion constraints from previous replan loops.
        # Formulation: x[i, j] == 0 for every (inc_id, spec_id) in excluded_set.
        for (exc_inc_id, exc_spec_id) in excluded_set:
            if (exc_inc_id, exc_spec_id) in x:
                model.Add(x[(exc_inc_id, exc_spec_id)] == 0)
                logger.debug(f"Exclusion constraint applied: {exc_spec_id} must not be assigned to {exc_inc_id}")
                        
        # 4. Modular Objective Components
        # Term 1: ARR matching reward
        arr_coefficients = []
        for inc in open_incidents:
            inc_id = inc.get("incident_id")
            cust_id = inc.get("customer_id")
            cust = customers_map.get(cust_id)
            try:
                arr_val = float(cust.get("arr") or 0.0) if cust else 0.0
            except (ValueError, TypeError):
                arr_val = 0.0
            arr = int(arr_val / 1000) if cust else 0  # In thousands to fit CP-SAT scale
            
            for spec in specialists:
                spec_id = spec.get("specialist_id")
                # Score proportional to ARR
                arr_coefficients.append(arr * weights.get("arr", 1) * x[(inc_id, spec_id)])
                
        # Term 2: SLA priority matching reward
        sla_coefficients = []
        for inc in open_incidents:
            inc_id = inc.get("incident_id")
            priority = str(inc.get("priority", "LOW")).upper()
            priority_score = {"CRITICAL": 100, "HIGH": 50, "MEDIUM": 20, "LOW": 5}.get(priority, 5)
            
            for spec in specialists:
                spec_id = spec.get("specialist_id")
                sla_coefficients.append(priority_score * weights.get("sla", 1) * x[(inc_id, spec_id)])
                
        # Term 3: Skill match quality reward
        skill_coefficients = []
        for inc in open_incidents:
            inc_id = inc.get("incident_id")
            req_skills = set(resolve_required_skills(inc))
            
            for spec in specialists:
                spec_id = spec.get("specialist_id")
                spec_skills = set(sk.lower() for sk in spec.get("skills", []))
                matched_count = len(req_skills & spec_skills)
                skill_coefficients.append(matched_count * weights.get("skills", 1) * x[(inc_id, spec_id)])
                
        # Term 4: Unassigned penalty (minimizing unassigned)
        unassigned_penalties = []
        penalty_weight = weights.get("unassigned_penalty", 10000)
        for inc in open_incidents:
            inc_id = inc.get("incident_id")
            unassigned_penalties.append(penalty_weight * u[inc_id])
            
        # Term 5: Workload balancing (Fairness)
        # Declaring a max workload variable M. M >= current_workload_j + sum(x[i, j])
        # We minimize M, which is equivalent to subtracting weight * M in a maximization objective.
        # Workloads range between 0 and max_capacity (typically < 10)
        max_possible_capacity = max((int(s.get("capacity") or 3) for s in specialists), default=10)
        M = model.NewIntVar(0, max_possible_capacity, "max_workload")
        for spec in specialists:
            spec_id = spec.get("specialist_id")
            current_workload = int(spec.get("current_workload") or 0)
            model.Add(
                M >= current_workload + sum(x[(inc.get("incident_id"), spec_id)] for inc in open_incidents)
            )
            
        # 5. Build Combined Objective
        # Maximize: ARR_Term + SLA_Term + Skill_Term - Unassigned_Penalty - Fairness_Penalty * M
        model.Maximize(
            sum(arr_coefficients) +
            sum(sla_coefficients) +
            sum(skill_coefficients) -
            sum(unassigned_penalties) -
            (weights.get("fairness", 1) * M)
        )
        
        # 6. Configure Solver & Time Limit
        solver = cp_model.CpSolver()
        time_limit = float(settings.solver_time_limit_seconds or 3.0)
        solver.parameters.max_time_in_seconds = time_limit
        
        # Solve
        status = solver.Solve(model)
        solving_time = (time_counter := time.perf_counter() - start_time)
        
        # 7. Parse allocations
        allocations = []
        unassigned = []
        
        is_feasible = (status in (cp_model.OPTIMAL, cp_model.FEASIBLE))
        
        if is_feasible:
            # Parse allocations from decision variables
            for inc in open_incidents:
                inc_id = inc.get("incident_id")
                req_skills = resolve_required_skills(inc)
                
                # Check if unassigned variable was set to 1
                if solver.Value(u[inc_id]) == 1:
                    unassigned.append(inc_id)
                    continue
                    
                assigned_spec = None
                for spec in specialists:
                    spec_id = spec.get("specialist_id")
                    if solver.Value(x[(inc_id, spec_id)]) == 1:
                        assigned_spec = spec
                        break
                        
                if assigned_spec:
                    allocations.append({
                        "incident_id": inc_id,
                        "specialist_id": assigned_spec["specialist_id"],
                        "matched_skills": list(set(req_skills) & set(assigned_spec.get("skills", [])))
                    })
                else:
                    unassigned.append(inc_id)
        else:
            logger.warning(f"CP-SAT solver failed to find feasible solution. Status: {status}")
            raise RuntimeError("CP-SAT solver returned infeasible or error status.")
            
        # Calculate metric summaries
        total_incidents = len(open_incidents)
        assigned_count = len(allocations)
        match_rate = (assigned_count / total_incidents * 100.0) if total_incidents > 0 else 100.0
        
        # Return structured candidate plan
        plan_id = f"PLAN-{profile_name.upper().replace(' ', '-')}"
        
        status_name = "UNKNOWN"
        if status == cp_model.OPTIMAL:
            status_name = "OPTIMAL"
        elif status == cp_model.FEASIBLE:
            if solving_time >= time_limit:
                status_name = "TIME_LIMIT"
            else:
                status_name = "FEASIBLE"
        elif status == cp_model.INFEASIBLE:
            status_name = "INFEASIBLE"
        elif status == cp_model.MODEL_INVALID:
            status_name = "MODEL_INVALID"
            
        from app.optimizer.profiles import get_profile_description
        return {
            "plan_id": plan_id,
            "profile": profile_name,
            "description": get_profile_description(profile_name),
            "objective_value": float(solver.ObjectiveValue()) if is_feasible else 0.0,
            "allocations": allocations,
            "unassigned_incidents": unassigned,
            "metrics": {
                "match_rate": match_rate,
                "unassigned_count": len(unassigned),
                "assigned_count": assigned_count
            },
            "metadata": {
                "solver_type": "CP-SAT",
                "solving_time_ms": round(solving_time * 1000, 1),
                "solver_status": status_name,
                "feasibility": is_feasible,
                "fallback_status": False
            }
        }
