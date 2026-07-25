import logging
from datetime import datetime
from uuid import uuid4
from typing import Dict, Any, List, Optional
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.models import BusinessGoal, AgentRun, RunEvent, GraphCheckpoint, StateSnapshot, EvidenceItem

logger = logging.getLogger("core-api.database.persistence")

async def save_business_goal(
    session: AsyncSession,
    goal_id: str,
    original_text: str,
    structured_goal_dict: Optional[Dict[str, Any]] = None,
    objective_profile: Optional[str] = None,
    time_horizon_minutes: Optional[int] = None
) -> BusinessGoal:
    """Creates or updates a BusinessGoal record."""
    stmt = select(BusinessGoal).where(BusinessGoal.goal_id == goal_id)
    res = await session.execute(stmt)
    goal = res.scalar_one_or_none()
    
    if not goal:
        goal = BusinessGoal(
            goal_id=goal_id,
            original_text=original_text,
            structured_goal_json=structured_goal_dict,
            objective_profile=objective_profile,
            time_horizon_minutes=time_horizon_minutes,
            created_at=datetime.utcnow()
        )
        session.add(goal)
    else:
        goal.structured_goal_json = structured_goal_dict
        goal.objective_profile = objective_profile
        goal.time_horizon_minutes = time_horizon_minutes
        
    await session.flush()
    return goal

async def save_agent_run(
    session: AsyncSession,
    run_id: str,
    scenario_id: str,
    status: str,
    goal_text: Optional[str] = None,
    state_version: int = 1,
    plan_version: int = 0,
    goal_id: Optional[str] = None,
    current_node: Optional[str] = None,
    replan_count: int = 0,
    recommended_plan_id: Optional[str] = None,
    completed_at: Optional[datetime] = None
) -> AgentRun:
    """Creates or updates an AgentRun record."""
    stmt = select(AgentRun).where(AgentRun.run_id == run_id)
    res = await session.execute(stmt)
    run = res.scalar_one_or_none()
    
    if not run:
        run = AgentRun(
            run_id=run_id,
            scenario_id=scenario_id,
            status=status,
            goal_text=goal_text,
            state_version=state_version,
            plan_version=plan_version,
            goal_id=goal_id,
            current_node=current_node,
            replan_count=replan_count,
            recommended_plan_id=recommended_plan_id,
            completed_at=completed_at,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        session.add(run)
    else:
        run.status = status
        run.state_version = state_version
        run.plan_version = plan_version
        if current_node:
            run.current_node = current_node
        run.replan_count = replan_count
        if recommended_plan_id:
            run.recommended_plan_id = recommended_plan_id
        if completed_at:
            run.completed_at = completed_at
        run.updated_at = datetime.utcnow()
        if goal_id:
            run.goal_id = goal_id
            
    await session.flush()
    return run

async def save_run_event(
    session: AsyncSession,
    run_id: str,
    sequence_number: int,
    event_type: str,
    source: str,
    summary: Optional[str] = None,
    payload_dict: Optional[Dict[str, Any]] = None,
    state_version: Optional[int] = None
) -> RunEvent:
    """Inserts a new audit log event in run_events."""
    event_id = str(uuid4())
    event = RunEvent(
        event_id=event_id,
        run_id=run_id,
        sequence_number=sequence_number,
        event_type=event_type,
        source=source,
        summary=summary,
        payload=payload_dict,
        state_version=state_version,
        created_at=datetime.utcnow()
    )
    session.add(event)
    await session.flush()
    return event

async def save_evidence_items(
    session: AsyncSession,
    run_id: str,
    state_version: int,
    collected_evidence: List[Dict[str, Any]]
) -> None:
    """Persists collected evidence logs to the evidence_items table, removing outdated version snapshots."""
    await session.execute(
        delete(EvidenceItem).where(
            EvidenceItem.run_id == run_id,
            EvidenceItem.state_version == state_version
        )
    )
    
    for ev in collected_evidence:
        payload = ev.get("payload", {})
        evidence_id = ev.get("evidence_id") or f"EV-{run_id}-{str(uuid4())[:8]}"
        
        item = EvidenceItem(
            evidence_id=evidence_id,
            run_id=run_id,
            state_version=state_version,
            source_service=ev.get("source_tool", "UNKNOWN"),
            entity_type=ev.get("entity_type", "GLOBAL"),
            entity_id=str(ev.get("entity_id", "GLOBAL")),
            field_name=ev.get("evidence_type", "METADATA"),
            value_json=payload,
            retrieved_at=datetime.utcnow(),
            freshness_status=ev.get("freshness_status", "FRESH"),
            quality_flags_json={"confidence": ev.get("confidence_level", "HIGH")},
            decision_critical=(ev.get("confidence_level") == "HIGH")
        )
        session.add(item)
        
    await session.flush()

async def save_state_snapshot(
    session: AsyncSession,
    run_id: str,
    state_version: int,
    state_json: Dict[str, Any],
    quality_category: str = "FRESH"
) -> StateSnapshot:
    """Persists a complete enterprise state database cache snapshot to state_snapshots."""
    snapshot_id = f"SNAP-{run_id}-{state_version}"
    
    stmt = select(StateSnapshot).where(StateSnapshot.snapshot_id == snapshot_id)
    res = await session.execute(stmt)
    snap = res.scalar_one_or_none()
    
    if not snap:
        snap = StateSnapshot(
            snapshot_id=snapshot_id,
            run_id=run_id,
            state_version=state_version,
            state_json=state_json,
            quality_category=quality_category,
            created_at=datetime.utcnow()
        )
        session.add(snap)
    else:
        snap.state_json = state_json
        snap.quality_category = quality_category
        
    await session.flush()
    return snap

async def save_graph_checkpoint(
    session: AsyncSession,
    run_id: str,
    state_version: int,
    node_name: str,
    checkpoint_json: Dict[str, Any]
) -> GraphCheckpoint:
    """Saves serialized graph checkpoint states."""
    checkpoint_id = f"CHK-{run_id}-{node_name}-{state_version}"
    
    stmt = select(GraphCheckpoint).where(GraphCheckpoint.checkpoint_id == checkpoint_id)
    res = await session.execute(stmt)
    chk = res.scalar_one_or_none()
    
    if not chk:
        chk = GraphCheckpoint(
            checkpoint_id=checkpoint_id,
            run_id=run_id,
            state_version=state_version,
            node_name=node_name,
            checkpoint_json=checkpoint_json,
            created_at=datetime.utcnow()
        )
        session.add(chk)
    else:
        chk.checkpoint_json = checkpoint_json
        
    await session.flush()
    return chk
