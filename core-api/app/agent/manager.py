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
            text("SELECT checkpoint_json FROM graph_checkpoints WHERE run_id = :r ORDER BY state_version DESC LIMIT 1"),
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
    recommended_plan: Optional[Dict[str, Any]] = None
) -> bool:
    """Restores the last checkpoint state, injects decision flags, and resumes execution."""
    checkpoint_state = await load_last_checkpoint(run_id)
    if not checkpoint_state:
        logger.warning(f"No checkpoint found to resume run: {run_id}")
        return False
        
    # Inject resumption context
    checkpoint_state["approval_status"] = approval_status
    if recommended_plan:
        checkpoint_state["recommended_plan"] = recommended_plan
        
    # Re-launch graph from the restored state
    asyncio.create_task(run_agent_background(checkpoint_state))
    return True
