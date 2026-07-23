"""Agent State module.

Declares the AgentState dictionary representing the current active variables of the
LangGraph orchestration loop.

NOTE: AgentState is intentionally minimal and only includes fields required for the current
phase (receive_goal -> complete_run).
Extension Points:
    - In future sets, it will be extended to include candidate_plans, approvals,
      execution logs, and auditing variables.
"""

from typing import TypedDict, Optional, List, Dict, Any

class AgentState(TypedDict, total=False):
    """The state payload passed between graph nodes in the LangGraph workflow.
    
    Fields:
        run_id: Unique string identifying the current agent run session.
        status: The current status of the agent execution flow.
        goal_text: The user-supplied natural-language goal string.
        structured_goal: The parsed goal representation (StructuredGoal dict).
        evidence_requirements: List of planned evidence requirements (EvidenceRequirement dicts).
        selected_tools: List of tools selected/skipped based on registry lookup.
        tool_results: List of execution results from the tool services.
        enterprise_state: Combined, normalized, and immutable portfolio state snapshot.
    """
    # Run Identity
    run_id: str
    status: str
    
    # Goal Details
    goal_text: str
    structured_goal: Optional[Dict[str, Any]]
    
    # Planning variables
    evidence_requirements: List[Dict[str, Any]]
    selected_tools: List[Dict[str, Any]]
    
    # Tool execution logs
    tool_results: List[Dict[str, Any]]
    
    # Combined snapshot
    enterprise_state: Optional[Dict[str, Any]]
