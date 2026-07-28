import pytest
from unittest.mock import patch, MagicMock
from app.optimizer.greedy import GreedyOptimizer
from app.optimizer.cpsat import CPSatOptimizer
from app.optimizer.solver import generate_optimization_plans

@pytest.fixture
def complex_portfolio():
    # Large strategic customer accounts
    customers = [
        {"customer_id": "CUS-MEGA", "arr": 900000.0},
        {"customer_id": "CUS-MED", "arr": 200000.0},
        {"customer_id": "CUS-SMALL", "arr": 20000.0}
    ]
    
    # Active escalations (incidents)
    # Total of 5 incidents, some requiring database skills, some requiring billing or integration
    escalations = [
        {"incident_id": "INC-1", "customer_id": "CUS-MEGA", "title": "DB timeout and database query error", "priority": "CRITICAL", "status": "OPEN"},
        {"incident_id": "INC-2", "customer_id": "CUS-MEGA", "title": "API Webhook integration failure", "priority": "CRITICAL", "status": "OPEN"},
        {"incident_id": "INC-3", "customer_id": "CUS-MED", "title": "SQL query locks and database bug", "priority": "HIGH", "status": "OPEN"},
        {"incident_id": "INC-4", "customer_id": "CUS-SMALL", "title": "Subscription payment billing invoice error", "priority": "MEDIUM", "status": "OPEN"},
        {"incident_id": "INC-5", "customer_id": "CUS-SMALL", "title": "API token webhook integration bug", "priority": "LOW", "status": "OPEN"}
    ]
    
    # Available specialists with capacities
    # Alice (capacity 2): database
    # Bob (capacity 2): integration
    # Priya (capacity 2): billing
    specialists = [
        {"specialist_id": "SPEC-ALICE", "name": "Alice", "skills": ["database"], "capacity": 2, "current_workload": 0},
        {"specialist_id": "SPEC-BOB", "name": "Bob", "skills": ["integration"], "capacity": 2, "current_workload": 0},
        {"specialist_id": "SPEC-PRIYA", "name": "Priya", "skills": ["billing"], "capacity": 2, "current_workload": 0}
    ]
    
    return customers, escalations, specialists

def test_compare_greedy_vs_cpsat(complex_portfolio):
    customers, escalations, specialists = complex_portfolio
    
    greedy = GreedyOptimizer()
    cpsat = CPSatOptimizer()
    
    greedy_plans = greedy.generate_plans(customers, escalations, specialists)
    cpsat_plans = cpsat.generate_plans(customers, escalations, specialists)
    
    assert len(greedy_plans) == 2  # Balanced, SLA-First
    assert len(cpsat_plans) == 4   # Balanced, SLA-First, Revenue-First, Fairness-First
    
    # 1. Compare Balanced profiles
    greedy_bal = next(p for p in greedy_plans if p["profile"] == "Balanced")
    cpsat_bal = next(p for p in cpsat_plans if p["profile"] == "Balanced")
    
    # Check that both solvers respect capacity constraints
    for plan in [greedy_bal, cpsat_bal]:
        workloads = {}
        for alloc in plan["allocations"]:
            spec_id = alloc["specialist_id"]
            workloads[spec_id] = workloads.get(spec_id, 0) + 1
        for spec_id, load in workloads.items():
            assert load <= 2  # Alice, Bob, Priya capacity is 2
            
    # Check solving times in metadata
    assert cpsat_bal["metadata"]["solver_type"] == "CP-SAT"
    assert "solving_time_ms" in cpsat_bal["metadata"]
    assert cpsat_bal["metadata"]["feasibility"] is True

def test_solver_gateway_fallback(complex_portfolio):
    customers, escalations, specialists = complex_portfolio
    
    from app.config.settings import settings
    orig_provider = settings.optimizer_provider
    orig_strategy = settings.optimization_strategy
    orig_allow_fallback = settings.optimizer_allow_fallback
    settings.optimizer_provider = "cp_sat"
    settings.optimization_strategy = None
    settings.optimizer_allow_fallback = True
    
    try:
        with patch("app.optimizer.cpsat.CPSatOptimizer.generate_plans", side_effect=Exception("CP-SAT crashed")):
            # Execute routing gateway
            plans = generate_optimization_plans(customers, escalations, specialists)
            
            # Verify fallback occurred and plans are generated via Greedy fallback
            assert len(plans) == 2
            for plan in plans:
                assert plan["metadata"]["fallback_status"] is True
                assert plan["metadata"]["solver_type"] == "Greedy (Fallback)"
    finally:
        settings.optimizer_provider = orig_provider
        settings.optimization_strategy = orig_strategy
        settings.optimizer_allow_fallback = orig_allow_fallback


def test_solver_gateway_does_not_silently_fallback(complex_portfolio):
    customers, escalations, specialists = complex_portfolio

    from app.config.settings import settings
    orig_provider = settings.optimizer_provider
    orig_allow_fallback = settings.optimizer_allow_fallback
    settings.optimizer_provider = "cp_sat"
    settings.optimizer_allow_fallback = False

    try:
        with patch("app.optimizer.cpsat.CPSatOptimizer.generate_plans", side_effect=Exception("CP-SAT crashed")):
            with pytest.raises(RuntimeError, match="Optimization failed under provider"):
                generate_optimization_plans(customers, escalations, specialists)
    finally:
        settings.optimizer_provider = orig_provider
        settings.optimizer_allow_fallback = orig_allow_fallback
