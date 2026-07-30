from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.preference_config import OptimizationProfile, PreferenceConfig
from app.database.models import AgentRun, RunEvent
from app.services.explanation_engine import ExplanationEngine
from app.services.manager_preference_service import ManagerPreferenceService
from app.services.recommendation_engine import RecommendationEngine


LearningStateValue = Literal["COLD_START", "LEARNING", "MATURE"]


class PreferenceRecommendationStatistics(BaseModel):
    shown: int = Field(ge=0)
    accepted: int = Field(ge=0)
    rejected: int = Field(ge=0)
    acceptance_rate: float = Field(ge=0.0, le=1.0)
    last_updated: datetime | None = None
    last_recommendation_timestamp: datetime | None = None


class RecentPreferenceDecision(BaseModel):
    event_id: str
    run_id: str
    decision: str
    selected_profile: str | None
    personalized_profile: str | None
    accepted_personalized: bool | None
    decision_reason: str | None
    decision_source: str | None
    goal_text: str | None
    created_at: datetime


class PreferenceSummary(BaseModel):
    learning_state: LearningStateValue
    total_decisions: int = Field(ge=0)
    runs_until_next_state: int = Field(ge=0)
    cold_start_runs_required: int = Field(ge=1)
    mature_runs_required: int = Field(ge=1)
    profile_counts: dict[str, int]
    dominant_profile: str | None
    dominant_profile_share: float = Field(ge=0.0, le=1.0)
    confidence: float = Field(ge=0.0, le=1.0)
    recommendation_statistics: PreferenceRecommendationStatistics
    learned_constraints: list[str]
    recent_decisions: list[RecentPreferenceDecision]
    updated_at: datetime


def _accepted_personalized(
    decision: str,
    selected_profile: str | None,
    personalized_profile: str | None,
) -> bool | None:
    if not personalized_profile:
        return None
    if decision != "APPROVED" or not selected_profile:
        return False
    return (
        PreferenceConfig.normalize_profile(selected_profile)
        == PreferenceConfig.normalize_profile(personalized_profile)
    )


async def get_preference_summary(
    session: AsyncSession,
    recent_limit: int = 5,
) -> PreferenceSummary:
    memory = await ManagerPreferenceService.load_memory(session)
    learning_state = ExplanationEngine.determine_learning_state(memory.total_runs)
    confidence = RecommendationEngine.calculate_confidence(memory)

    profile_counts = {
        profile.value: max(0, int(memory.profile_counts.get(profile.value, 0)))
        for profile in OptimizationProfile
    }
    selected_total = sum(profile_counts.values())
    dominant_profile = (
        max(profile_counts, key=profile_counts.get)
        if selected_total > 0
        else None
    )
    dominant_share = (
        profile_counts[dominant_profile] / selected_total
        if dominant_profile
        else 0.0
    )

    if learning_state.value == "COLD_START":
        runs_until_next_state = max(
            0,
            PreferenceConfig.COLD_START_RUNS - memory.total_runs,
        )
    elif learning_state.value == "LEARNING":
        runs_until_next_state = max(
            0,
            PreferenceConfig.MATURE_LEARNING_RUNS - memory.total_runs,
        )
    else:
        runs_until_next_state = 0

    statement = (
        select(RunEvent, AgentRun.goal_text)
        .outerjoin(AgentRun, AgentRun.run_id == RunEvent.run_id)
        .where(RunEvent.event_type == "PREFERENCE_MEM_UPDATED")
        .order_by(RunEvent.created_at.desc())
        .limit(recent_limit)
    )
    rows = (await session.execute(statement)).all()
    recent_decisions: list[RecentPreferenceDecision] = []
    for event, goal_text in rows:
        payload = event.payload or {}
        decision = str(payload.get("decision") or "UNKNOWN").upper()
        selected_profile = payload.get("selected_profile")
        personalized_profile = payload.get("personalized_profile")
        recent_decisions.append(
            RecentPreferenceDecision(
                event_id=event.event_id,
                run_id=event.run_id or "UNKNOWN",
                decision=decision,
                selected_profile=(
                    str(selected_profile)
                    if selected_profile
                    else None
                ),
                personalized_profile=(
                    str(personalized_profile)
                    if personalized_profile
                    else None
                ),
                accepted_personalized=_accepted_personalized(
                    decision,
                    str(selected_profile) if selected_profile else None,
                    str(personalized_profile) if personalized_profile else None,
                ),
                decision_reason=(
                    str(payload.get("decision_reason"))
                    if payload.get("decision_reason")
                    else None
                ),
                decision_source=(
                    str(payload.get("decision_source"))
                    if payload.get("decision_source")
                    else None
                ),
                goal_text=goal_text,
                created_at=event.created_at,
            )
        )

    stats = memory.recommendation_statistics
    acceptance_rate = stats.accepted / stats.shown if stats.shown > 0 else 0.0

    return PreferenceSummary(
        learning_state=learning_state.value,
        total_decisions=memory.total_runs,
        runs_until_next_state=runs_until_next_state,
        cold_start_runs_required=PreferenceConfig.COLD_START_RUNS,
        mature_runs_required=PreferenceConfig.MATURE_LEARNING_RUNS,
        profile_counts=profile_counts,
        dominant_profile=dominant_profile,
        dominant_profile_share=dominant_share,
        confidence=confidence,
        recommendation_statistics=PreferenceRecommendationStatistics(
            shown=stats.shown,
            accepted=stats.accepted,
            rejected=stats.rejected,
            acceptance_rate=acceptance_rate,
            last_updated=stats.last_updated,
            last_recommendation_timestamp=stats.last_recommendation_timestamp,
        ),
        learned_constraints=memory.learned_constraints,
        recent_decisions=recent_decisions,
        updated_at=memory.updated_at,
    )
