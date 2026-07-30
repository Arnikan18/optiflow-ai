from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from sqlalchemy import String, Integer, Boolean, DateTime, ForeignKey, Text, JSON
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

class Base(DeclarativeBase):
    pass


def utc_now() -> datetime:
    return datetime.now(timezone.utc)

class BusinessGoal(Base):
    __tablename__ = "business_goals"
    
    goal_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    original_text: Mapped[str] = mapped_column(Text, nullable=False)
    structured_goal_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    objective_profile: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    time_horizon_minutes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    policy_version: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    prompt_template_version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    created_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class SystemSetting(Base):
    """Encrypted, versioned application setting owned by Core."""

    __tablename__ = "system_settings"

    setting_key: Mapped[str] = mapped_column(String(100), primary_key=True)
    encrypted_value: Mapped[str] = mapped_column(Text, nullable=False)
    schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )


class AgentRun(Base):
    __tablename__ = "agent_runs"
    
    run_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    scenario_id: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(50), nullable=False)
    goal_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    state_version: Mapped[int] = mapped_column(Integer, default=1)
    plan_version: Mapped[int] = mapped_column(Integer, default=0)
    created_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # New Version 4 columns
    goal_id: Mapped[Optional[str]] = mapped_column(String(100), ForeignKey("business_goals.goal_id"), nullable=True)
    current_node: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    replan_count: Mapped[int] = mapped_column(Integer, default=0)
    recommended_plan_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

class RunEvent(Base):
    __tablename__ = "run_events"
    
    event_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    run_id: Mapped[Optional[str]] = mapped_column(String(100), ForeignKey("agent_runs.run_id"), nullable=True)
    sequence_number: Mapped[int] = mapped_column(Integer, nullable=False)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    source: Mapped[str] = mapped_column(String(100), nullable=False)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    payload: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    state_version: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

class GraphCheckpoint(Base):
    __tablename__ = "graph_checkpoints"
    
    checkpoint_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    run_id: Mapped[Optional[str]] = mapped_column(String(100), ForeignKey("agent_runs.run_id"), nullable=True)
    state_version: Mapped[int] = mapped_column(Integer, default=1)
    node_name: Mapped[str] = mapped_column(String(100), nullable=False)
    checkpoint_json: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

class StateSnapshot(Base):
    __tablename__ = "state_snapshots"
    
    snapshot_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    run_id: Mapped[Optional[str]] = mapped_column(String(100), ForeignKey("agent_runs.run_id"), nullable=True)
    state_version: Mapped[int] = mapped_column(Integer, default=1)
    state_json: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    quality_category: Mapped[str] = mapped_column(String(50), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

class EvidenceItem(Base):
    __tablename__ = "evidence_items"
    
    evidence_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    run_id: Mapped[Optional[str]] = mapped_column(String(100), ForeignKey("agent_runs.run_id"), nullable=True)
    state_version: Mapped[int] = mapped_column(Integer, default=1)
    source_service: Mapped[str] = mapped_column(String(50), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(100), nullable=False)
    field_name: Mapped[str] = mapped_column(String(100), nullable=False)
    value_json: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    source_updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    freshness_status: Mapped[str] = mapped_column(String(50), nullable=False)
    quality_flags_json: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    decision_critical: Mapped[bool] = mapped_column(Boolean, default=False)


class ManagerPreference(Base):
    __tablename__ = "manager_preferences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    preference_json: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )


class SimulationRun(Base):
    __tablename__ = "simulation_runs"

    simulation_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    scenario_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    scenario_name: Mapped[str] = mapped_column(String(200), nullable=False)
    mode: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    current_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    current_stage: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    current_timeline_position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    processed_events: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    pending_events: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    last_event: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    enterprise_changed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    notification_status: Mapped[str] = mapped_column(String(32), nullable=False, default="NOT_REQUIRED")
    auto_advance: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    paused_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now, onupdate=utc_now)


class SimulationEventHistory(Base):
    __tablename__ = "simulation_event_history"

    event_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    simulation_id: Mapped[Optional[str]] = mapped_column(String(100), index=True, nullable=True)
    scenario_id: Mapped[Optional[str]] = mapped_column(String(100), index=True, nullable=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    processing_status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    enterprise_changed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    payload: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    changed_entities: Mapped[list[Dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    error_details: Mapped[list[Dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    notification_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    notification_status: Mapped[str] = mapped_column(String(32), nullable=False, default="NOT_REQUIRED")
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, unique=True, index=True)
    request_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    applied_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)


class SimulationNotification(Base):
    __tablename__ = "simulation_notifications"

    notification_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    simulation_id: Mapped[Optional[str]] = mapped_column(String(100), index=True, nullable=True)
    scenario_id: Mapped[Optional[str]] = mapped_column(String(100), index=True, nullable=True)
    event_id: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    payload: Mapped[Dict[str, Any]] = mapped_column(JSON, nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    request_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    delivered_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    acknowledged_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now)

