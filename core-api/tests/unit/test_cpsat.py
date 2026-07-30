import pytest
from ortools.sat.python import cp_model

from app.optimizer.cpsat import CPSatOptimizer

@pytest.fixture
def sample_data():
    customers = [
        {"customer_id": "CUS-A", "arr": 250000.0},
        {"customer_id": "CUS-B", "arr": 50000.0}
    ]
    
    escalations = [
        {"incident_id": "INC-1", "customer_id": "CUS-A", "title": "Database timeout", "priority": "CRITICAL", "status": "OPEN"},
        {"incident_id": "INC-2", "customer_id": "CUS-B", "title": "Billing subscription issues", "priority": "HIGH", "status": "OPEN"}
    ]
    
    specialists = [
        {"specialist_id": "SPEC-ALICE", "name": "Alice", "skills": ["database"], "capacity": 2, "current_workload": 0},
        {"specialist_id": "SPEC-BOB", "name": "Bob", "skills": ["billing"], "capacity": 2, "current_workload": 0}
    ]
    return customers, escalations, specialists

def test_cpsat_solver_feasible(sample_data):
    customers, escalations, specialists = sample_data
    optimizer = CPSatOptimizer()
    
    plans = optimizer.generate_plans(customers, escalations, specialists)
    assert len(plans) == 4
    assert [plan["profile_id"] for plan in plans] == ["BALANCED", "SLA_FIRST", "REVENUE_FIRST", "FAIRNESS_FIRST"]
    
    for plan in plans:
        assert plan["feasible"] is True
        assert plan["solver_status"] in {"OPTIMAL", "FEASIBLE", "TIME_LIMIT"}
        assert "generated_at" in plan
        assert "solve_time_ms" in plan
        assert "objective_weights" in plan
        assert "arr_protected" in plan["metrics"]
        assert "sla_score" in plan["metrics"]
        assert "fairness_score" in plan["metrics"]
        assert "workload_distribution" in plan["metrics"]
        assert "maximum_specialist_utilisation" in plan["metrics"]
        assert "average_specialist_utilisation" in plan["metrics"]
        assert "context_switching_count" in plan["metrics"]
        assert plan["metrics"]["assigned_count"] == 2
        assert len(plan["allocations"]) == 2
        
        # Verify Alice gets INC-1 (database skill required)
        alice_alloc = next(a for a in plan["allocations"] if a["specialist_id"] == "SPEC-ALICE")
        assert alice_alloc["incident_id"] == "INC-1"
        
        # Verify Bob gets INC-2 (billing skill required)
        bob_alloc = next(a for a in plan["allocations"] if a["specialist_id"] == "SPEC-BOB")
        assert bob_alloc["incident_id"] == "INC-2"

def test_cpsat_solver_capacity_limit(sample_data):
    customers, escalations, specialists = sample_data
    optimizer = CPSatOptimizer()
    
    # Restrict Alice's capacity to 0
    specialists[0]["capacity"] = 0
    
    plans = optimizer.generate_plans(customers, escalations, specialists)
    assert len(plans) == 4
    for plan in plans:
        # INC-1 requires database skill, but Alice is at full capacity (0 capacity).
        # It must be left unassigned.
        assert "INC-1" in plan["unassigned_incidents"]
        assert len(plan["allocations"]) == 1


def test_cpsat_respects_excluded_pairs(sample_data):
    customers, escalations, specialists = sample_data

    plans = CPSatOptimizer().generate_plans(
        customers,
        escalations,
        specialists,
        excluded_pairs=[{"incident_id": "INC-1", "specialist_id": "SPEC-ALICE"}],
    )

    for plan in plans:
        allocation_pairs = {
            (item["incident_id"], item["specialist_id"])
            for item in plan["allocations"]
        }
        assert ("INC-1", "SPEC-ALICE") not in allocation_pairs
        assert "INC-1" in plan["unassigned_incidents"]


def test_cpsat_preserves_existing_assignments(sample_data):
    customers, escalations, specialists = sample_data
    escalations[0]["status"] = "IN_PROGRESS"
    escalations[0]["assigned_specialist_id"] = "SPEC-ALICE"
    specialists[0]["current_workload"] = 1

    plans = CPSatOptimizer().generate_plans(customers, escalations, specialists)

    for plan in plans:
        allocation_ids = {item["incident_id"] for item in plan["allocations"]}
        assert "INC-1" not in allocation_ids
        assert allocation_ids == {"INC-2"}
        assert plan["metrics"]["assigned_count"] == 1


def test_cpsat_profiles_have_distinct_weights(sample_data):
    customers, escalations, specialists = sample_data
    plans = CPSatOptimizer().generate_plans(customers, escalations, specialists)

    weight_sets = {plan["profile_id"]: tuple(sorted(plan["objective_weights"].items())) for plan in plans}
    assert len(set(weight_sets.values())) == 4
    assert weight_sets["SLA_FIRST"] != weight_sets["REVENUE_FIRST"]
    assert weight_sets["FAIRNESS_FIRST"] != weight_sets["BALANCED"]


def test_cpsat_output_is_deterministic(sample_data):
    customers, escalations, specialists = sample_data
    optimizer = CPSatOptimizer()

    first = optimizer.generate_plans(customers, escalations, specialists)
    second = optimizer.generate_plans(list(reversed(customers)), list(reversed(escalations)), list(reversed(specialists)))

    first_pairs = {
        plan["profile_id"]: sorted((item["incident_id"], item["specialist_id"]) for item in plan["assignments"])
        for plan in first
    }
    second_pairs = {
        plan["profile_id"]: sorted((item["incident_id"], item["specialist_id"]) for item in plan["assignments"])
        for plan in second
    }
    assert second_pairs == first_pairs


def test_cpsat_empty_incident_and_empty_specialist_inputs(sample_data):
    customers, _, specialists = sample_data
    no_incidents = CPSatOptimizer().generate_plans(customers, [], specialists)
    assert len(no_incidents) == 4
    assert all(plan["feasible"] is True for plan in no_incidents)
    assert all(plan["assignments"] == [] for plan in no_incidents)
    assert all(plan["metrics"]["match_rate"] == 100.0 for plan in no_incidents)

    _, escalations, _ = sample_data
    no_specialists = CPSatOptimizer().generate_plans(customers, escalations, [])
    assert len(no_specialists) == 4
    assert all(plan["assignments"] == [] for plan in no_specialists)
    assert all(set(plan["unassigned_incidents"]) == {"INC-1", "INC-2"} for plan in no_specialists)


def test_cpsat_skills_mismatch_returns_unassigned(sample_data):
    customers, escalations, _ = sample_data
    specialists = [
        {"specialist_id": "SPEC-NO-MATCH", "name": "No Match", "skills": ["integration"], "capacity": 2, "current_workload": 0}
    ]

    plans = CPSatOptimizer().generate_plans(customers, escalations, specialists)

    assert all(plan["feasible"] is True for plan in plans)
    assert all(plan["assignments"] == [] for plan in plans)
    assert all(set(plan["unassigned_incidents"]) == {"INC-1", "INC-2"} for plan in plans)


def test_cpsat_infeasible_input_returns_structured_profile(sample_data):
    customers, escalations, _ = sample_data
    specialists = [
        {"specialist_id": "SPEC-OVER", "name": "Over Capacity", "skills": ["database", "billing"], "capacity": 1, "current_workload": 2}
    ]

    plans = CPSatOptimizer().generate_plans(customers, escalations, specialists)

    assert len(plans) == 4
    for plan in plans:
        assert plan["feasible"] is False
        assert plan["solver_status"] == "INFEASIBLE"
        assert plan["assignments"] == []
        assert plan["failure_reason"]


def test_cpsat_metric_calculations(sample_data):
    customers, escalations, specialists = sample_data
    balanced = CPSatOptimizer().generate_plans(customers, escalations, specialists)[0]

    assert balanced["metrics"]["arr_protected"] == 300000.0
    assert balanced["metrics"]["sla_breaches_avoided"] == 2
    assert balanced["metrics"]["sla_score"] == 100.0
    assert balanced["metrics"]["context_switching_count"] == 0
    assert balanced["metrics"]["unassigned_count"] == 0


def test_cpsat_context_switching_calculation(sample_data):
    customers, escalations, specialists = sample_data
    specialists[0]["current_workload"] = 1

    plans = CPSatOptimizer().generate_plans(customers, escalations, specialists)

    assert any(plan["metrics"]["context_switching_count"] >= 1 for plan in plans)


def test_cpsat_timeout_status_mapping():
    assert CPSatOptimizer._solver_status_name(cp_model.FEASIBLE, 10.0, 0.001) == "TIME_LIMIT"
    assert CPSatOptimizer._solver_status_name(cp_model.UNKNOWN, 10.0, 0.001) == "TIME_LIMIT"


def test_profile_weights_loading():
    from app.optimizer.profiles import get_profile_weights
    import os
    
    # Check default Balanced
    w = get_profile_weights("Balanced")
    assert w["arr"] == 8
    assert w["skills"] == 10
    
    # Test environment override
    os.environ["OPTIMIZER_WEIGHTS_BALANCED_SKILLS"] = "99"
    try:
        w_override = get_profile_weights("Balanced")
        assert w_override["skills"] == 99
    finally:
        del os.environ["OPTIMIZER_WEIGHTS_BALANCED_SKILLS"]

