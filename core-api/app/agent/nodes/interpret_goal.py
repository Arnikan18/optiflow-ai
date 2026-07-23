from app.agent.state import AgentState
from app.goals.interpreter import interpret_goal_text

async def interpret_goal(state: AgentState) -> dict:
    goal_text = state.get("goal_text", "")
    structured_goal = interpret_goal_text(goal_text)
    print("[interpret_goal]\nGoal interpreted")
    # structured_goal needs to be stored as a dictionary in AgentState
    return {"structured_goal": structured_goal.model_dump()}
