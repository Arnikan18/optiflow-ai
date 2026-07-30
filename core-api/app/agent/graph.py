"""LangGraph workflow definition.

Builds and compiles the StateGraph for OptiFlow AI, incorporating the Version 4
conditional routing paths, clarification loops, and human-in-the-loop approval gates.
"""

from langgraph.graph import END, START, StateGraph
from app.agent.state import AgentState
from app.agent.nodes.receive_goal import receive_goal
from app.agent.nodes.interpret_goal import interpret_goal
from app.agent.nodes.validate_goal import validate_goal
from app.agent.nodes.plan_evidence import plan_evidence
from app.agent.nodes.select_tools import select_tools
from app.agent.nodes.execute_tools import execute_tools
from app.agent.nodes.build_state import build_state
from app.agent.nodes.pause_for_clarification import pause_for_clarification
from app.agent.nodes.evaluate_quality import evaluate_quality
from app.agent.nodes.generate_plans import generate_plans
from app.agent.nodes.generate_personalized_plan import generate_personalized_plan
from app.agent.nodes.pause_for_approval import pause_for_approval
from app.agent.nodes.execute_saga import execute_saga
from app.agent.nodes.complete_run import complete_run
from app.agent.nodes.update_preference_memory import update_preference_memory
from app.agent.nodes.enterprise_monitor import enterprise_monitor


def route_after_monitoring(state: AgentState) -> str:
    """Routes the workflow based on whether replanning is needed under simulation mode."""
    if not state.get("simulation_mode"):
        return "evaluate_quality"
    if state.get("status") == "REPLANNING":
        return "evaluate_quality"
    if state.get("replan_needed", True):
        return "evaluate_quality"
    return "complete_run"


def route_after_validation(state: AgentState) -> str:
    """Routes the workflow based on goal validation outcomes."""
    status = state.get("status")
    if status == "NEEDS_CLARIFICATION":
        return "pause_for_clarification"
    elif status == "FAILED_SAFE":
        return "complete_run"
    return "plan_evidence"


def route_after_approval(state: AgentState) -> str:
    """Routes the workflow based on the human approval status."""
    app_status = state.get("approval_status")
    if app_status in ("APPROVED", "REJECTED", "MODIFY"):
        return "update_preference_memory"
    
    # Halt execution and wait at END for approval request resume (checkpoint resume)
    return END


def route_after_preference_update(state: AgentState) -> str:
    """Routes the workflow after updating the preference memory based on approval status."""
    app_status = state.get("approval_status")
    if app_status == "APPROVED":
        return "execute_saga"
    elif app_status == "MODIFY":
        return "interpret_goal"
    return "complete_run"


def route_after_saga(state: AgentState) -> str:
    """Routes the workflow after SAGA execution.
    
    REPLANNING: a specialist rejected or timed out — loop back to interpret_goal
    so the CP-SAT optimizer can regenerate all four profiles with the excluded
    specialist-incident pair as a hard constraint.
    
    All other outcomes (EXECUTED, FAILED_SAGA) proceed to complete_run.
    """
    if state.get("status") == "REPLANNING":
        return "interpret_goal"
    return "complete_run"


def build_graph() -> StateGraph:
    """Creates, nodes-registers, and compiles the Version 4 StateGraph workflow."""
    graph = StateGraph(AgentState)
    
    # 1. Register all nodes
    graph.add_node("receive_goal", receive_goal)
    graph.add_node("interpret_goal", interpret_goal)
    graph.add_node("validate_goal", validate_goal)
    graph.add_node("pause_for_clarification", pause_for_clarification)
    graph.add_node("plan_evidence", plan_evidence)
    graph.add_node("select_tools", select_tools)
    graph.add_node("execute_tools", execute_tools)
    graph.add_node("build_state", build_state)
    graph.add_node("evaluate_quality", evaluate_quality)
    graph.add_node("generate_plans", generate_plans)
    graph.add_node("generate_personalized_plan", generate_personalized_plan)
    graph.add_node("pause_for_approval", pause_for_approval)
    graph.add_node("execute_saga", execute_saga)
    graph.add_node("complete_run", complete_run)
    graph.add_node("update_preference_memory", update_preference_memory)
    graph.add_node("enterprise_monitor", enterprise_monitor)
    
    # 2. Establish links and conditional routing paths
    graph.add_edge(START, "receive_goal")
    graph.add_edge("receive_goal", "interpret_goal")
    graph.add_edge("interpret_goal", "validate_goal")
    
    # Conditional edge after validation check
    graph.add_conditional_edges(
        "validate_goal",
        route_after_validation,
        {
            "pause_for_clarification": "pause_for_clarification",
            "complete_run": "complete_run",
            "plan_evidence": "plan_evidence"
        }
    )
    
    # Clarification Pause routes to END (waiting for user resume)
    graph.add_edge("pause_for_clarification", END)
    
    # Main path continues
    graph.add_edge("plan_evidence", "select_tools")
    graph.add_edge("select_tools", "execute_tools")
    graph.add_edge("execute_tools", "build_state")
    graph.add_edge("build_state", "enterprise_monitor")
    
    # Conditional edge after monitoring checks
    graph.add_conditional_edges(
        "enterprise_monitor",
        route_after_monitoring,
        {
            "evaluate_quality": "evaluate_quality",
            "complete_run": "complete_run"
        }
    )
    graph.add_edge("evaluate_quality", "generate_plans")
    graph.add_edge("generate_plans", "generate_personalized_plan")
    graph.add_edge("generate_personalized_plan", "pause_for_approval")
    
    # Conditional edge after human control approval gate
    graph.add_conditional_edges(
        "pause_for_approval",
        route_after_approval,
        {
            "update_preference_memory": "update_preference_memory",
            "__end__": END
        }
    )
    
    # After preference update, route to SAGA, replanning, or completion
    graph.add_conditional_edges(
        "update_preference_memory",
        route_after_preference_update,
        {
            "execute_saga": "execute_saga",
            "interpret_goal": "interpret_goal",
            "complete_run": "complete_run"
        }
    )
    
    # After SAGA: conditional routing — REPLANNING loops back, all else completes
    graph.add_conditional_edges(
        "execute_saga",
        route_after_saga,
        {
            "interpret_goal": "interpret_goal",
            "complete_run": "complete_run"
        }
    )
    graph.add_edge("complete_run", END)
    
    return graph

# Compiled graph reference
compiled_graph = build_graph().compile()
