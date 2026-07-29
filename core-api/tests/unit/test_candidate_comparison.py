import pytest
from app.services.candidate_comparison_builder import CandidateComparisonBuilder, CandidatePlanSummary

def test_dto_mapping_and_defaults():
    """Verify DTO maps all summary and metrics fields correctly."""
    plans = [
        {
            "plan_id": "PLAN-BALANCED",
            "profile": "Balanced",
            "objective_value": 75.5,
            "metrics": {
                "sla_score": 90.0,
                "arr_protected": 200000.0,
                "fairness_score": 85.0,
                "context_switching_score": 95.0
            }
        }
    ]
    customers = [
        {"customer_id": "C-1", "arr": 250000.0}
    ]
    
    summaries = CandidateComparisonBuilder.build_summaries(
        plans=plans,
        customers=customers,
        recommended_plan_id="PLAN-BALANCED",
        personalized_reason="Preferences met."
    )
    
    assert len(summaries) == 1
    summary = summaries[0]
    assert isinstance(summary, CandidatePlanSummary)
    assert summary.profile == "Balanced"
    assert summary.objective_score == 75.5
    assert summary.sla_score == 90.0
    # 200K protected / 250K total = 80.0%
    assert summary.revenue_score == 80.0
    assert summary.fairness_score == 85.0
    assert summary.workload_score == 95.0
    assert summary.selected is True
    assert summary.recommendation_reason == "Preferences met."
    assert summary.rank == 1

def test_rank_ordering():
    """Verify plans are ranked sequentially starting at 1 by objective score."""
    plans = [
        {"plan_id": "P-BAL", "profile": "Balanced", "objective_value": 80.0},
        {"plan_id": "P-SLA", "profile": "SLA First", "objective_value": 95.0},
        {"plan_id": "P-REV", "profile": "Revenue First", "objective_value": 90.0}
    ]
    
    summaries = CandidateComparisonBuilder.build_summaries(plans=plans, customers=[])
    
    # Ranks should order plans: SLA First (1), Revenue First (2), Balanced (3)
    assert summaries[0].profile == "SLA First"
    assert summaries[0].rank == 1
    assert summaries[1].profile == "Revenue First"
    assert summaries[1].rank == 2
    assert summaries[2].profile == "Balanced"
    assert summaries[2].rank == 3

def test_recommendation_independence():
    """Verify that rank (optimizer order) and selected (recommendation engine choice) are independent."""
    plans = [
        {"plan_id": "P-BAL", "profile": "Balanced", "objective_value": 100.0}, # Rank #1
        {"plan_id": "P-SLA", "profile": "SLA First", "objective_value": 85.0}   # Rank #2
    ]
    
    summaries = CandidateComparisonBuilder.build_summaries(
        plans=plans,
        customers=[],
        recommended_plan_id="P-SLA", # RecommendationEngine chooses Rank #2
        personalized_reason="SLA prioritized"
    )
    
    # Assert Rank #1 is not selected
    assert summaries[0].profile == "Balanced"
    assert summaries[0].rank == 1
    assert summaries[0].selected is False
    assert summaries[0].recommendation_reason == "Best overall balance"
    
    # Assert Rank #2 is selected
    assert summaries[1].profile == "SLA First"
    assert summaries[1].rank == 2
    assert summaries[1].selected is True
    assert summaries[1].recommendation_reason == "SLA prioritized"

def test_default_explanation_mapping():
    """Verify that default profile reasons are loaded correctly from config mappings."""
    plans = [
        {"plan_id": "P-BAL", "profile": "Balanced", "objective_value": 80.0},
        {"plan_id": "P-SLA", "profile": "SLA First", "objective_value": 70.0},
        {"plan_id": "P-REV", "profile": "Revenue First", "objective_value": 60.0},
        {"plan_id": "P-FAI", "profile": "Fairness First", "objective_value": 50.0}
    ]
    
    summaries = CandidateComparisonBuilder.build_summaries(plans=plans, customers=[])
    
    assert summaries[0].recommendation_reason == "Best overall balance"
    assert summaries[1].recommendation_reason == "Highest SLA protection"
    assert summaries[2].recommendation_reason == "Highest revenue preservation"
    assert summaries[3].recommendation_reason == "Best workload distribution"

def test_revenue_score_edge_cases():
    """Verify revenue score handles normal ARR, zero ARR, and empty customers list safely."""
    plans = [
        {
            "plan_id": "P-BAL",
            "profile": "Balanced",
            "objective_value": 80.0,
            "metrics": {"arr_protected": 50000.0}
        }
    ]
    
    # 1. Zero ARR
    summaries_zero = CandidateComparisonBuilder.build_summaries(
        plans=plans,
        customers=[{"customer_id": "C-1", "arr": 0.0}]
    )
    assert summaries_zero[0].revenue_score == 100.0
    
    # 2. Empty customers list
    summaries_empty = CandidateComparisonBuilder.build_summaries(
        plans=plans,
        customers=[]
    )
    assert summaries_empty[0].revenue_score == 100.0
    
    # 3. Normal values
    summaries_normal = CandidateComparisonBuilder.build_summaries(
        plans=plans,
        customers=[{"customer_id": "C-1", "arr": 100000.0}]
    )
    assert summaries_normal[0].revenue_score == 50.0

def test_empty_candidate_list():
    """Verify builder returns an empty list when plans are empty."""
    assert CandidateComparisonBuilder.build_summaries(plans=[], customers=[]) == []

def test_missing_metrics_graceful_fallback():
    """Verify builder defaults missing metrics to 0.0 or match_rate fallback values."""
    plans = [
        {
            "plan_id": "P-BAL",
            "profile": "Balanced",
            "objective_value": 80.0,
            "metrics": {
                "match_rate": 75.0
            }
        }
    ]
    
    summaries = CandidateComparisonBuilder.build_summaries(plans=plans, customers=[])
    summary = summaries[0]
    
    assert summary.objective_score == 80.0
    assert summary.sla_score == 75.0
    assert summary.revenue_score == 75.0
    assert summary.fairness_score == 75.0
    assert summary.workload_score == 75.0

def test_optimizer_compatibility():
    """Verify builder is compatible with mock CP-SAT and Greedy plan structures."""
    # 1. CP-SAT plan structure
    cpsat_plans = [{
        "plan_id": "PLAN-BALANCED",
        "profile": "Balanced",
        "objective_value": 85000.0,
        "metrics": {
            "arr_protected": 120000.0,
            "sla_score": 95.5,
            "fairness_score": 88.0,
            "context_switching_score": 90.0
        }
    }]
    cpsat_sum = CandidateComparisonBuilder.build_summaries(cpsat_plans, [{"arr": 150000.0}])
    assert cpsat_sum[0].sla_score == 95.5
    assert cpsat_sum[0].revenue_score == 80.0
    
    # 2. Greedy plan structure (fallback mode, no detailed scores)
    greedy_plans = [{
        "plan_id": "PLAN-BALANCED",
        "profile": "Balanced",
        "objective_value": 72.0,
        "metrics": {
            "match_rate": 80.0,
            "assigned_count": 8,
            "unassigned_count": 2
        }
    }]
    greedy_sum = CandidateComparisonBuilder.build_summaries(greedy_plans, [])
    assert greedy_sum[0].sla_score == 80.0
    assert greedy_sum[0].revenue_score == 80.0

def test_builder_non_mutation():
    """Verify that CandidateComparisonBuilder does not mutate its inputs (pure transformation)."""
    import copy
    plans = [
        {
            "plan_id": "P-BAL",
            "profile": "Balanced",
            "objective_value": 80.0,
            "metrics": {
                "sla_score": 90.0,
                "arr_protected": 50000.0,
                "fairness_score": 85.0,
                "context_switching_score": 95.0
            }
        }
    ]
    customers = [
        {"customer_id": "C-1", "arr": 100000.0}
    ]
    
    plans_copy = copy.deepcopy(plans)
    customers_copy = copy.deepcopy(customers)
    
    CandidateComparisonBuilder.build_summaries(
        plans=plans,
        customers=customers,
        recommended_plan_id="P-BAL",
        personalized_reason="Override"
    )
    
    assert plans == plans_copy
    assert customers == customers_copy

def test_single_candidate_plan():
    """Verify builder behaves correctly when exactly one candidate plan is passed."""
    plans = [{"plan_id": "P-BAL", "profile": "Balanced", "objective_value": 75.0}]
    summaries = CandidateComparisonBuilder.build_summaries(plans=plans, customers=[])
    assert len(summaries) == 1
    assert summaries[0].rank == 1
    assert summaries[0].selected is False
    assert summaries[0].recommendation_reason == "Best overall balance"

def test_large_arr_values():
    """Verify that very large ARR values do not cause overflow and scale correctly."""
    plans = [
        {
            "plan_id": "P-BAL",
            "profile": "Balanced",
            "objective_value": 80.0,
            "metrics": {"arr_protected": 25000000.0} # $25M protected
        }
    ]
    customers = [
        {"customer_id": "C-1", "arr": 100000000.0} # $100M total
    ]
    summaries = CandidateComparisonBuilder.build_summaries(plans=plans, customers=customers)
    # $25M / $100M = 25.0%
    assert summaries[0].revenue_score == 25.0

def test_json_serialization():
    """Verify DTO models serialize cleanly to JSON/dict format for API response compatibility."""
    plans = [
        {
            "plan_id": "P-BAL",
            "profile": "Balanced",
            "objective_value": 85.2,
            "metrics": {
                "sla_score": 92.5,
                "arr_protected": 45000.0,
                "fairness_score": 90.0,
                "context_switching_score": 88.0
            }
        }
    ]
    summaries = CandidateComparisonBuilder.build_summaries(plans=plans, customers=[])
    for s in summaries:
        serialized = s.model_dump(mode="json")
        assert serialized["profile"] == "Balanced"
        assert serialized["objective_score"] == 85.2
        assert serialized["sla_score"] == 92.5
        assert serialized["selected"] is False
        assert serialized["rank"] == 1


