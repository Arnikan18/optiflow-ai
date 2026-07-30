from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional

class TriggerEventMetadata(BaseModel):
    event_id: Optional[str] = None
    event_type: str
    priority: Optional[str] = None
    timestamp: Optional[str] = None

class DecisionMetadata(BaseModel):
    decision_id: str
    run_id: str
    scenario_id: Optional[str] = None
    timestamp: str
    timeline_position: int
    trigger_event: Optional[TriggerEventMetadata] = None

class ExecutiveSummary(BaseModel):
    headline: str
    summary_text: str

class ReasoningStep(BaseModel):
    step_name: str
    status: str  # E.g. "COMPLETED", "SKIPPED", "PENDING"
    description: Optional[str] = None

class EvidenceSummary(BaseModel):
    crm: List[str] = Field(default_factory=list)
    incident: List[str] = Field(default_factory=list)
    workforce: List[str] = Field(default_factory=list)
    optimizer: List[str] = Field(default_factory=list)

class DecisionReasoning(BaseModel):
    reasons: List[str]
    evidence_used: EvidenceSummary
    reasoning_path: List[ReasoningStep]

class CandidateAlternative(BaseModel):
    profile: str
    rank: int
    objective_score: float
    sla_score: float
    revenue_score: float
    fairness_score: float
    workload_score: float
    selection_or_rejection_reason: str

class ConfidenceReport(BaseModel):
    score: float
    level: str
    reason: str

class RecommendationDetail(BaseModel):
    selected_profile: str
    selection_reason: str
    confidence: ConfidenceReport
    alternatives: List[CandidateAlternative]

class OperationalAction(BaseModel):
    action_text: str
    assignee: str
    target: str
    priority: str
    expected_effect: str

class BusinessKPI(BaseModel):
    metric_name: str
    display_value: str
    impact_level: str  # E.g. "HIGH_POSITIVE", "NEUTRAL", "MINOR_NEGATIVE"

class TradeoffSummary(BaseModel):
    benefits: List[str]
    drawbacks: List[str]

class BusinessImpactSummary(BaseModel):
    kpis: List[BusinessKPI]
    tradeoffs: TradeoffSummary

class DecisionOutcome(BaseModel):
    status: str = "Pending"
    observed_impact: Optional[str] = None
    evaluation_notes: Optional[str] = None

class DecisionExplanation(BaseModel):
    metadata: DecisionMetadata
    executive_summary: ExecutiveSummary
    reasoning: DecisionReasoning
    recommendation: RecommendationDetail
    business_impact: BusinessImpactSummary
    actions: List[OperationalAction]
    outcome: DecisionOutcome

class PresentationOutput(BaseModel):
    business_summary: str
    change_summary: str
    markdown_report: Optional[str] = None
