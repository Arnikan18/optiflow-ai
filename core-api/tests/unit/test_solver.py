import pytest
from app.optimizer.solver import (
    score_incident_priority,
    resolve_required_skills,
    generate_optimization_plans
)

def test_score_incident_priority():
    customers_map = {
        "CUS-ALPHA": {"customer_id": "CUS-ALPHA", "arr": 250000.0},  # weight points: +2.5
        "CUS-BETA": {"customer_id": "CUS-BETA", "arr": 0.0}
    }
    
    # 1. Critical priority incident (base 100)
    inc1 = {"priority": "CRITICAL", "customer_id": "CUS-ALPHA"}
    assert score_incident_priority(inc1, customers_map) == 102.5
    
    # 2. Low priority incident (base 5)
    inc2 = {"priority": "LOW", "customer_id": "CUS-BETA"}
    assert score_incident_priority(inc2, customers_map) == 5.0

def test_resolve_required_skills():
    # 1. Payload skills list present
    inc1 = {"skills": ["Python", "SQL"]}
    assert resolve_required_skills(inc1) == ["python", "sql"]
    
    # 2. Text keyword matching
    inc2 = {"title": "Database connection timeout", "description": "Need DBA help"}
    assert "database" in resolve_required_skills(inc2)
    
    inc3 = {"title": "OAuth security login failure"}
    assert "security" in resolve_required_skills(inc3)

def test_generate_optimization_plans():
    customers = [
        {"customer_id": "CUS-ALPHA", "arr": 500000.0}
    ]
    
    escalations = [
        {"incident_id": "INC-01", "customer_id": "CUS-ALPHA", "title": "API timeout error", "priority": "CRITICAL", "status": "OPEN"},
        {"incident_id": "INC-02", "customer_id": "CUS-ALPHA", "title": "DB connection breach", "priority": "HIGH", "status": "OPEN"}
    ]
    
    specialists = [
        # Alice matches integration (from "API" keyword)
        {"specialist_id": "SPEC-ALICE", "name": "Alice", "skills": ["integration"], "capacity": 2, "current_workload": 0},
        # Bob matches database (from "DB" keyword)
        {"specialist_id": "SPEC-BOB", "name": "Bob", "skills": ["database"], "capacity": 1, "current_workload": 0}
    ]
    
    plans = generate_optimization_plans(customers, escalations, specialists)
    assert len(plans) == 2
    
    # Verify profiles
    profiles = {p["profile"]: p for p in plans}
    assert "Balanced" in profiles
    assert "SLA-First" in profiles
    
    # Verify allocations
    balanced = profiles["Balanced"]
    assert len(balanced["allocations"]) == 2
    
    alloc_map = {a["incident_id"]: a["specialist_id"] for a in balanced["allocations"]}
    assert alloc_map["INC-01"] == "SPEC-ALICE"
    assert alloc_map["INC-02"] == "SPEC-BOB"
