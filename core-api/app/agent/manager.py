import logging
import asyncio
import json
from typing import Dict, Any, Optional
from sqlalchemy import text
from app.agent.graph import compiled_graph
from app.database.session import async_session

logger = logging.getLogger("core-api.agent.manager")

async def run_agent_background(state: Dict[str, Any]) -> None:
    """Invokes the compiled StateGraph in a background task."""
    run_id = state.get("run_id", "unknown")
    print(f"[ExecutionManager] Starting background task for run: {run_id}")
    try:
        await compiled_graph.ainvoke(state)
        print(f"[ExecutionManager] Background task completed for run: {run_id}")
    except Exception as e:
        logger.error(f"[ExecutionManager] Critical error running agent graph for {run_id}: {str(e)}")

async def start_new_run(run_id: str, goal_text: str) -> None:
    """Prepares and launches a new agent graph run in the background."""
    state = {
        "run_id": run_id,
        "goal_text": goal_text,
        "status": "RECEIVED"
    }
    # Spawn background task
    asyncio.create_task(run_agent_background(state))

async def load_last_checkpoint(run_id: str) -> Optional[Dict[str, Any]]:
    """Loads the latest checkpoint state dictionary for the run from database."""
    async with async_session() as session:
        res = await session.execute(
            text("SELECT checkpoint_json FROM graph_checkpoints WHERE run_id = :r ORDER BY created_at DESC LIMIT 1"),
            {"r": run_id}
        )
        row = res.fetchone()
        if row and row[0]:
            # SQLite or Postgres might return str or dict depending on driver/JSON type mapping
            val = row[0]
            if isinstance(val, str):
                return json.loads(val)
            return val
    return None

async def resume_run_from_checkpoint(
    run_id: str, 
    approval_status: str, 
    recommended_plan: Optional[Dict[str, Any]] = None,
    clarification_reply: Optional[str] = None,
    decision_reason: Optional[str] = None,
    decision_source: Optional[str] = None,
) -> bool:
    """Restores the last checkpoint state, injects decision flags, and resumes execution."""
    checkpoint_state = await load_last_checkpoint(run_id)
    if not checkpoint_state:
        logger.warning(f"No checkpoint found to resume run: {run_id}")
        return False
        
    # Inject resumption context
    checkpoint_state["approval_status"] = approval_status
    if approval_status == "MODIFY" and decision_reason:
        original_goal = checkpoint_state.get("goal_text", "")
        checkpoint_state["goal_text"] = (
            f"{original_goal} (Manager modification: {decision_reason})"
        )
    if recommended_plan:
        checkpoint_state["recommended_plan"] = recommended_plan
    if decision_reason:
        checkpoint_state["decision_reason"] = decision_reason
    if decision_source:
        checkpoint_state["decision_source"] = decision_source
    if clarification_reply:
        # Append clarification context to the original goal text
        orig_goal = checkpoint_state.get("goal_text", "")
        checkpoint_state["goal_text"] = f"{orig_goal} (Clarification: {clarification_reply})"
        checkpoint_state["clarification_resolved"] = True
        # Remove ambiguities from structured goal so validator doesn't loop
        if "structured_goal" in checkpoint_state and checkpoint_state["structured_goal"]:
            checkpoint_state["structured_goal"]["ambiguities"] = []
        
    # Re-launch graph from the restored state
    asyncio.create_task(run_agent_background(checkpoint_state))
    return True
