import pytest
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
    
    for plan in plans:
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

def test_profile_weights_loading():
    from app.optimizer.profiles import get_profile_weights
    import os
    
    # Check default Balanced
    w = get_profile_weights("Balanced")
    assert w["arr"] == 1
    assert w["skills"] == 5
    
    # Test environment override
    os.environ["OPTIMIZER_WEIGHTS_BALANCED_SKILLS"] = "99"
    try:
        w_override = get_profile_weights("Balanced")
        assert w_override["skills"] == 99
    finally:
        del os.environ["OPTIMIZER_WEIGHTS_BALANCED_SKILLS"]

