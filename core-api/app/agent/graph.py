"""LangGraph workflow definition.

Builds and compiles the linear StateGraph for the first implementation phases
representing the progression of goal reception, parsing, tool routing, and state building.

Intended Usage:
    `compiled_graph` is called asynchronously (ainvoke) to run the core reasoning loop.

Extension Points:
    - In future sets, conditional edges will be introduced for tool failures,
      re-planning loops, human approval gate, and execution SAGAs.
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
from app.agent.nodes.complete_run import complete_run

def build_graph() -> StateGraph:
    """Creates, nodes-registers, and compiles the linear StateGraph workflow."""
    graph = StateGraph(AgentState)
    
    # Register nodes
    graph.add_node("receive_goal", receive_goal)
    graph.add_node("interpret_goal", interpret_goal)
    graph.add_node("validate_goal", validate_goal)
    graph.add_node("plan_evidence", plan_evidence)
    graph.add_node("select_tools", select_tools)
    graph.add_node("execute_tools", execute_tools)
    graph.add_node("build_state", build_state)
    graph.add_node("complete_run", complete_run)
    
    # Establish edges (linear workflow for current phase)
    graph.add_edge(START, "receive_goal")
    graph.add_edge("receive_goal", "interpret_goal")
    graph.add_edge("interpret_goal", "validate_goal")
    graph.add_edge("validate_goal", "plan_evidence")
    graph.add_edge("plan_evidence", "select_tools")
    graph.add_edge("select_tools", "execute_tools")
    graph.add_edge("execute_tools", "build_state")
    graph.add_edge("build_state", "complete_run")
    graph.add_edge("complete_run", END)
    
    return graph

# Compiled graph reference used by backend controllers
compiled_graph = build_graph().compile()
