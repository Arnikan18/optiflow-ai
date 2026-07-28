import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List

from ortools.sat.python import cp_model

from app.config.settings import settings
from app.optimizer.base import BaseOptimizer


logger = logging.getLogger("core-api.optimizer.cpsat")

LEGACY_PROFILE_NAMES = {
    "BALANCED": "Balanced",
    "SLA_FIRST": "SLA-First",
    "REVENUE_FIRST": "Revenue-First",
    "FAIRNESS_FIRST": "Fairness-First",
}


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class CPSatOptimizer(BaseOptimizer):
    """Google OR-Tools CP-SAT portfolio-level scheduling optimizer strategy."""

    def generate_plans(
        self,
        customers: List[Dict[str, Any]],
        escalations: List[Dict[str, Any]],
        specialists: List[Dict[str, Any]],
        excluded_pairs: List[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Generate profile-specific CP-SAT plans.

        excluded_pairs contains specialist/incident pairs that a replan must avoid,
        for example after a specialist rejects a previous assignment request.
        """
        from app.optimizer.profiles import PROFILE_ORDER, get_profile_definition, get_profile_weights

        excluded_pairs = excluded_pairs or []
        selected_profiles = PROFILE_ORDER if settings.generate_all_optimization_profiles else ("BALANCED",)
        plans: list[dict[str, Any]] = []
        for profile_id in selected_profiles:
            profile = get_profile_definition(profile_id)
            weights = get_profile_weights(profile_id)
            plan = self._solve_portfolio(profile, weights, customers, escalations, specialists, excluded_pairs)
            plans.append(plan)

        self._annotate_duplicate_assignments(plans)
        return plans

    def _solve_portfolio(
        self,
        profile: Dict[str, Any],
        weights: Dict[str, int],
        customers: List[Dict[str, Any]],
        escalations: List[Dict[str, Any]],
        specialists: List[Dict[str, Any]],
        excluded_pairs: List[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        from app.optimizer.solver import resolve_required_skills

        excluded_pairs = excluded_pairs or []
        excluded_set = {
            (str(ep["incident_id"]), str(ep["specialist_id"]))
            for ep in excluded_pairs
            if ep.get("incident_id") and ep.get("specialist_id")
        }

        profile_id = str(profile["profile_id"])
        profile_name = str(profile["profile_name"])
        legacy_profile_name = LEGACY_PROFILE_NAMES[profile_id]
        generated_at = utc_timestamp()
        start_time = time.perf_counter()

        customers_map = {
            str(customer.get("customer_id")): customer
            for customer in sorted(customers, key=lambda item: str(item.get("customer_id") or ""))
            if customer.get("customer_id")
        }
        open_incidents = [
            incident
            for incident in sorted(escalations, key=lambda item: str(item.get("incident_id") or ""))
            if str(incident.get("status", "")).upper() in ("OPEN", "UNASSIGNED", "ASSIGNED", "IN_PROGRESS")
        ]
        ordered_specialists = sorted(specialists, key=lambda item: str(item.get("specialist_id") or ""))

        model = cp_model.CpModel()
        x: dict[tuple[str, str], cp_model.IntVar] = {}
        u: dict[str, cp_model.IntVar] = {}

        for incident in open_incidents:
            incident_id = str(incident.get("incident_id") or "")
            u[incident_id] = model.NewBoolVar(f"unassigned_{incident_id}")
            for specialist in ordered_specialists:
                specialist_id = str(specialist.get("specialist_id") or "")
                x[(incident_id, specialist_id)] = model.NewBoolVar(f"assign_{incident_id}_{specialist_id}")

        for incident in open_incidents:
            incident_id = str(incident.get("incident_id") or "")
            model.Add(
                u[incident_id]
                + sum(x[(incident_id, str(specialist.get("specialist_id") or ""))] for specialist in ordered_specialists)
                == 1
            )

        for specialist in ordered_specialists:
            specialist_id = str(specialist.get("specialist_id") or "")
            capacity = self._int_value(specialist.get("capacity"), default=3)
            current_workload = self._int_value(specialist.get("current_workload"), default=0)
            model.Add(
                current_workload
                + sum(x[(str(incident.get("incident_id") or ""), specialist_id)] for incident in open_incidents)
                <= capacity
            )

        for incident in open_incidents:
            incident_id = str(incident.get("incident_id") or "")
            required_skills = set(resolve_required_skills(incident))
            for specialist in ordered_specialists:
                specialist_id = str(specialist.get("specialist_id") or "")
                specialist_skills = {str(skill).lower() for skill in specialist.get("skills", [])}
                if required_skills and not (required_skills & specialist_skills):
                    model.Add(x[(incident_id, specialist_id)] == 0)

        for incident_id, specialist_id in excluded_set:
            if (incident_id, specialist_id) in x:
                model.Add(x[(incident_id, specialist_id)] == 0)
                logger.debug(
                    "Exclusion constraint applied: %s must not be assigned to %s",
                    specialist_id,
                    incident_id,
                )

        arr_terms = []
        sla_terms = []
        skill_terms = []
        context_switch_terms = []
        unassigned_penalties = []

        for incident in open_incidents:
            incident_id = str(incident.get("incident_id") or "")
            customer = customers_map.get(str(incident.get("customer_id") or ""))
            arr_thousands = int(self._float_value(customer.get("arr") if customer else 0.0) / 1000)
            priority_score = self._sla_priority_score(incident)
            required_skills = set(resolve_required_skills(incident))

            unassigned_penalties.append(weights.get("unassigned_penalty", 10000) * u[incident_id])

            for specialist in ordered_specialists:
                specialist_id = str(specialist.get("specialist_id") or "")
                specialist_skills = {str(skill).lower() for skill in specialist.get("skills", [])}
                matched_count = len(required_skills & specialist_skills)
                existing_workload = self._int_value(specialist.get("current_workload"), default=0)

                arr_terms.append(arr_thousands * weights.get("arr", 1) * x[(incident_id, specialist_id)])
                sla_terms.append(priority_score * weights.get("sla", 1) * x[(incident_id, specialist_id)])
                skill_terms.append(matched_count * weights.get("skills", 1) * x[(incident_id, specialist_id)])
                if existing_workload > 0:
                    context_switch_terms.append(weights.get("context_switch", 1) * x[(incident_id, specialist_id)])

        max_capacity = max((self._int_value(specialist.get("capacity"), default=3) for specialist in ordered_specialists), default=1)
        max_workload = model.NewIntVar(0, max_capacity + len(open_incidents), "max_workload")
        for specialist in ordered_specialists:
            specialist_id = str(specialist.get("specialist_id") or "")
            current_workload = self._int_value(specialist.get("current_workload"), default=0)
            model.Add(
                max_workload
                >= current_workload
                + sum(x[(str(incident.get("incident_id") or ""), specialist_id)] for incident in open_incidents)
            )

        model.Maximize(
            sum(arr_terms)
            + sum(sla_terms)
            + sum(skill_terms)
            - sum(unassigned_penalties)
            - (weights.get("fairness", 1) * max_workload)
            - sum(context_switch_terms)
        )

        solver = cp_model.CpSolver()
        time_limit = float(settings.cp_sat_time_limit_seconds or 5.0)
        solver.parameters.max_time_in_seconds = time_limit
        solver.parameters.random_seed = int(settings.cp_sat_random_seed or 42)
        solver.parameters.num_search_workers = 1

        status = solver.Solve(model)
        solve_time_ms = round((time.perf_counter() - start_time) * 1000, 1)
        status_name = self._solver_status_name(status, solve_time_ms, time_limit)
        feasible = status in (cp_model.OPTIMAL, cp_model.FEASIBLE)

        assignments: list[dict[str, Any]] = []
        unassigned: list[str] = []
        failure_reason: str | None = None

        if feasible:
            for incident in open_incidents:
                incident_id = str(incident.get("incident_id") or "")
                if solver.Value(u[incident_id]) == 1:
                    unassigned.append(incident_id)
                    continue

                assigned_specialist = None
                for specialist in ordered_specialists:
                    specialist_id = str(specialist.get("specialist_id") or "")
                    if solver.Value(x[(incident_id, specialist_id)]) == 1:
                        assigned_specialist = specialist
                        break

                if assigned_specialist is None:
                    unassigned.append(incident_id)
                    continue

                required_skills = set(resolve_required_skills(incident))
                specialist_skills = {str(skill).lower() for skill in assigned_specialist.get("skills", [])}
                assignments.append(
                    {
                        "incident_id": incident_id,
                        "specialist_id": str(assigned_specialist["specialist_id"]),
                        "matched_skills": sorted(required_skills & specialist_skills),
                    }
                )
        else:
            unassigned = [str(incident.get("incident_id") or "") for incident in open_incidents]
            failure_reason = self._failure_reason(status_name)

        metrics = self._calculate_metrics(customers_map, open_incidents, ordered_specialists, assignments, unassigned)
        objective_value = float(solver.ObjectiveValue()) if feasible else 0.0

        logger.info(
            "cp_sat_profile_solved",
            extra={
                "structured": {
                    "optimizer_provider": "cp_sat",
                    "profile_id": profile_id,
                    "solver_status": status_name,
                    "runtime_ms": solve_time_ms,
                    "feasible": feasible,
                    "objective_value": objective_value,
                }
            },
        )

        plan_id = f"PLAN-{profile_id}"
        return {
            "plan_id": plan_id,
            "profile_id": profile_id,
            "profile_name": profile_name,
            "profile": legacy_profile_name,
            "description": str(profile["description"]),
            "assignments": assignments,
            "allocations": assignments,
            "objective_weights": dict(weights),
            "objective_value": objective_value,
            "solver_status": status_name,
            "feasible": feasible,
            "generated_at": generated_at,
            "solve_time_ms": solve_time_ms,
            "failure_reason": failure_reason,
            "unassigned_incidents": unassigned,
            "metrics": metrics,
            "metadata": {
                "solver_type": "CP-SAT",
                "solver_status": status_name,
                "solving_time_ms": solve_time_ms,
                "feasibility": feasible,
                "fallback_status": False,
                "random_seed": int(settings.cp_sat_random_seed or 42),
                "time_limit_seconds": time_limit,
            },
        }

    @staticmethod
    def _annotate_duplicate_assignments(plans: list[dict[str, Any]]) -> None:
        signatures: dict[tuple[tuple[str, str], ...], list[dict[str, Any]]] = {}
        for plan in plans:
            signature = tuple(
                sorted(
                    (str(item.get("incident_id") or ""), str(item.get("specialist_id") or ""))
                    for item in plan.get("assignments", [])
                )
            )
            signatures.setdefault(signature, []).append(plan)

        for duplicate_group in signatures.values():
            if len(duplicate_group) < 2:
                continue
            explanation = (
                "Profiles produced the same assignment because hard constraints, capacity, skills, "
                "and deterministic ordering left no better distinct feasible allocation."
            )
            for plan in duplicate_group:
                plan["metadata"]["duplicate_assignment_explanation"] = explanation

    @staticmethod
    def _solver_status_name(status: int, solve_time_ms: float, time_limit_seconds: float) -> str:
        if status == cp_model.OPTIMAL:
            return "OPTIMAL"
        if status == cp_model.FEASIBLE:
            return "TIME_LIMIT" if solve_time_ms >= time_limit_seconds * 1000 else "FEASIBLE"
        if status == cp_model.INFEASIBLE:
            return "INFEASIBLE"
        if status == cp_model.MODEL_INVALID:
            return "MODEL_INVALID"
        return "TIME_LIMIT" if solve_time_ms >= time_limit_seconds * 1000 else "UNKNOWN"

    @staticmethod
    def _failure_reason(status_name: str) -> str:
        reasons = {
            "INFEASIBLE": "No allocation satisfies the current hard constraints.",
            "MODEL_INVALID": "The CP-SAT model was invalid for the provided input.",
            "TIME_LIMIT": "The CP-SAT solver reached its configured time limit before finding a feasible solution.",
        }
        return reasons.get(status_name, f"CP-SAT did not return a feasible solution. solver_status={status_name}")

    @staticmethod
    def _int_value(value: Any, *, default: int = 0) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _float_value(value: Any, *, default: float = 0.0) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _sla_priority_score(incident: dict[str, Any]) -> int:
        return {
            "CRITICAL": 100,
            "HIGH": 50,
            "MEDIUM": 20,
            "LOW": 5,
        }.get(str(incident.get("priority", "LOW")).upper(), 5)

    def _calculate_metrics(
        self,
        customers_map: dict[str, dict[str, Any]],
        incidents: list[dict[str, Any]],
        specialists: list[dict[str, Any]],
        assignments: list[dict[str, Any]],
        unassigned: list[str],
    ) -> dict[str, Any]:
        assignment_by_incident = {item["incident_id"]: item["specialist_id"] for item in assignments}
        workloads = {
            str(specialist.get("specialist_id") or ""): self._int_value(specialist.get("current_workload"), default=0)
            for specialist in specialists
        }
        capacities = {
            str(specialist.get("specialist_id") or ""): max(self._int_value(specialist.get("capacity"), default=1), 1)
            for specialist in specialists
        }
        for specialist_id in assignment_by_incident.values():
            workloads[specialist_id] = workloads.get(specialist_id, 0) + 1

        arr_protected = 0.0
        sla_score_numerator = 0
        sla_score_denominator = 0
        sla_breaches_avoided = 0
        for incident in incidents:
            incident_id = str(incident.get("incident_id") or "")
            customer = customers_map.get(str(incident.get("customer_id") or ""))
            priority_score = self._sla_priority_score(incident)
            sla_score_denominator += priority_score
            if incident_id not in assignment_by_incident:
                continue
            arr_protected += self._float_value(customer.get("arr") if customer else 0.0)
            sla_score_numerator += priority_score
            if str(incident.get("priority", "")).upper() in ("CRITICAL", "HIGH"):
                sla_breaches_avoided += 1

        utilisation = {
            specialist_id: workloads[specialist_id] / capacities.get(specialist_id, 1)
            for specialist_id in workloads
        }
        max_utilisation = max(utilisation.values(), default=0.0)
        average_utilisation = sum(utilisation.values()) / len(utilisation) if utilisation else 0.0
        workload_values = list(workloads.values())
        workload_spread = (max(workload_values) - min(workload_values)) if workload_values else 0
        fairness_score = max(0.0, 100.0 - (workload_spread * 25.0))
        context_switching_count = sum(
            1
            for assignment in assignments
            if self._int_value(
                next(
                    (
                        specialist.get("current_workload")
                        for specialist in specialists
                        if str(specialist.get("specialist_id") or "") == assignment["specialist_id"]
                    ),
                    0,
                ),
                default=0,
            )
            > 0
        )

        total_incidents = len(incidents)
        assigned_count = len(assignments)
        sla_score = (sla_score_numerator / sla_score_denominator * 100.0) if sla_score_denominator else 100.0

        return {
            "arr_protected": round(arr_protected, 2),
            "sla_breaches_avoided": sla_breaches_avoided,
            "sla_score": round(sla_score, 2),
            "sla_risk_reduction": round(sla_score, 2),
            "fairness_score": round(fairness_score, 2),
            "workload_distribution": workloads,
            "maximum_specialist_utilisation": round(max_utilisation, 4),
            "average_specialist_utilisation": round(average_utilisation, 4),
            "context_switching_count": context_switching_count,
            "context_switching_score": max(0, 100 - (context_switching_count * 10)),
            "unassigned_incidents": list(unassigned),
            "unassigned_count": len(unassigned),
            "assigned_count": assigned_count,
            "match_rate": round((assigned_count / total_incidents * 100.0) if total_incidents else 100.0, 2),
            "feasibility_status": "FEASIBLE" if assigned_count or not incidents else "PARTIAL",
        }
