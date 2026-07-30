from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.preferences.service import get_preference_summary
from app.services.manager_preference_service import (
    PreferenceMemory,
    RecommendationStats,
)


@pytest.mark.asyncio
async def test_preference_summary_exposes_memory_and_recent_decisions():
    now = datetime.now(timezone.utc)
    memory = PreferenceMemory(
        total_runs=12,
        profile_counts={
            "BALANCED": 2,
            "SLA_FIRST": 8,
            "REVENUE_FIRST": 1,
            "FAIRNESS_FIRST": 1,
        },
        recommendation_statistics=RecommendationStats(
            shown=6,
            accepted=5,
            rejected=1,
            last_updated=now,
        ),
        learned_constraints=["Protect renewals"],
        updated_at=now,
    )
    event = SimpleNamespace(
        event_id="EVENT-1",
        run_id="RUN-1",
        payload={
            "decision": "APPROVED",
            "selected_profile": "SLA First",
            "personalized_profile": "SLA-First",
        },
        created_at=now,
    )
    result = SimpleNamespace(all=lambda: [(event, "Protect urgent banking renewals")])
    session = AsyncMock()
    session.execute.return_value = result

    with patch(
        "app.preferences.service.ManagerPreferenceService.load_memory",
        new=AsyncMock(return_value=memory),
    ):
        summary = await get_preference_summary(session, recent_limit=5)

    assert summary.learning_state == "LEARNING"
    assert summary.total_decisions == 12
    assert summary.runs_until_next_state == 8
    assert summary.dominant_profile == "SLA_FIRST"
    assert summary.dominant_profile_share == pytest.approx(8 / 12)
    assert summary.recommendation_statistics.acceptance_rate == pytest.approx(5 / 6)
    assert summary.learned_constraints == ["Protect renewals"]
    assert summary.recent_decisions[0].selected_profile == "SLA First"
    assert summary.recent_decisions[0].accepted_personalized is True


@pytest.mark.asyncio
async def test_preference_summary_handles_empty_memory():
    memory = PreferenceMemory()
    result = SimpleNamespace(all=list)
    session = AsyncMock()
    session.execute.return_value = result

    with patch(
        "app.preferences.service.ManagerPreferenceService.load_memory",
        new=AsyncMock(return_value=memory),
    ):
        summary = await get_preference_summary(session)

    assert summary.learning_state == "COLD_START"
    assert summary.total_decisions == 0
    assert summary.runs_until_next_state == 5
    assert summary.dominant_profile is None
    assert summary.confidence == 0
    assert summary.recent_decisions == []
