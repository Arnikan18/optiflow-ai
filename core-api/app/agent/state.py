"""Agent State module.

Declares the AgentState dictionary representing the current active variables of the
LangGraph orchestration loop, expanded to conform to the Version 4 technical spec.
"""

from typing import TypedDict, Optional, List, Dict, Any

class AgentState(TypedDict, total=False):
    """The state payload passed between graph nodes in the LangGraph workflow.
    
    Contains all Version 4 canonical run state fields alongside Phase 3A backward compatibility attributes.
    """
    # 1. Existing Phase 3A baseline fields (for compatibility)
    run_id: str
    status: str
    goal_text: str
    llm_mode: str
    llm_provider: str
    llm_model: str
    structured_goal: Optional[Dict[str, Any]]
    evidence_requirements: List[Dict[str, Any]]
    selected_tools: List[Dict[str, Any]]
    tool_results: List[Dict[str, Any]]
    enterprise_state: Optional[Dict[str, Any]]

    # 2. Version 4 Canonical Run State fields (Section 7.2 of PDF)
    current_node: str
    state_version: int
    active_policies: Dict[str, Any]
    required_evidence: List[Dict[str, Any]]
    collected_evidence: List[Dict[str, Any]]
    confidence_report: Optional[Dict[str, Any]]
    autonomy_risk_report: Optional[Dict[str, Any]]
    source_freshness: Dict[str, Any]

    data_conflicts: List[Dict[str, Any]]
    missing_fields: List[str]
    consequence_estimates: List[Dict[str, Any]]
    candidate_plans: List[Dict[str, Any]]
    recommended_plan: Optional[Dict[str, Any]]
    policy_results: Dict[str, Any]
    approval_status: str
    approved_state_version: int
    approved_plan_version: int
    execution_actions: List[Dict[str, Any]]
    execution_receipts: List[Dict[str, Any]]
    monitoring_events: List[Dict[str, Any]]
    replan_count: int
    excluded_specialist_incidents: List[Dict[str, Any]]
    personalized_recommendation: Optional[Dict[str, Any]]
    created_at: str
    updated_at: str
    clarification_resolved: bool

