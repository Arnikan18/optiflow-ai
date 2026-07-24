from pydantic import BaseModel, Field
from typing import Generic, TypeVar, Any, Optional, List
from datetime import datetime
from optiflow_shared.enums import EvidenceType, EvidenceImportance, ObjectiveType, FreshnessStatus

T = TypeVar('T')

class ToolResponseEnvelope(BaseModel, Generic[T]):
    requestId: str
    scenarioId: str
    sourceService: str
    sourceUpdatedAt: str  # ISO timestamp
    retrievedAt: str     # ISO timestamp
    data: T

class TimeHorizon(BaseModel):
    value: int = Field(gt=0)
    unit: str

class StructuredGoal(BaseModel):
    summary: str
    objectives: List[ObjectiveType]
    time_horizon: TimeHorizon
    hard_constraints: List[str]
    soft_preferences: List[str]
    requested_actions: List[str]
    ambiguities: List[str]
    unsupported_requests: List[str]
    interpretation_notes: List[str]

class EvidenceRequirement(BaseModel):
    evidence_type: EvidenceType
    importance: EvidenceImportance
    entity_scope: str
    reason: str
    freshness_seconds: int

class EvidenceItem(BaseModel):
    evidence_id: str
    run_id: str
    evidence_type: EvidenceType
    entity_type: Optional[str] = None
    entity_id: Optional[str] = None
    source_tool: str
    source_record_id: Optional[str] = None
    payload: dict
    retrieved_at: datetime
    source_updated_at: Optional[datetime] = None
    fresh_until: Optional[datetime] = None
    freshness_status: FreshnessStatus
    confidence_level: str

class ToolExecutionResult(BaseModel):
    tool_call_id: str
    run_id: str
    tool_name: str
    endpoint: str
    method: str
    purpose: Optional[str] = None
    reason_selected: Optional[str] = None
    status: str
    latency_ms: Optional[int] = None
    retry_count: int = 0
    request_summary: Optional[dict] = None
    response_summary: Optional[dict] = None
    error_category: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

class GoalValidationResult(BaseModel):
    valid: bool
    clarification_required: bool
    blocking_reasons: List[str]
    warnings: List[str]
    clarification_question: Optional[str] = None
