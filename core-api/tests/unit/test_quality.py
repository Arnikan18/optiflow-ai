import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from app.agent.nodes.evaluate_quality import evaluate_quality, _compute_confidence


# ── Unit tests for the confidence scoring formula ────────────────────────────

def test_confidence_no_issues():
    """Perfect data: no missing fields, no conflicts, fresh snapshot → score 100."""
    score, report = _compute_confidence(
        missing_fields=[],
        data_conflicts=[],
        retrieved_at=None,
    )
    assert score == 100.0
    assert report["grade"] == "HIGH"
    assert report["completeness_penalty"] == 0
    assert report["conflict_penalty"] == 0
    assert report["freshness_penalty"] == 0


def test_confidence_missing_fields():
    """Two missing fields → completeness penalty of 2 × 15 = 30 → score 70."""
    score, report = _compute_confidence(
        missing_fields=["field_a", "field_b"],
        data_conflicts=[],
        retrieved_at=None,
    )
    assert report["completeness_penalty"] == 30
    assert report["conflict_penalty"] == 0
    assert score == 70.0
    assert report["grade"] == "MEDIUM"


def test_confidence_data_conflicts():
    """One conflict → conflict penalty of 20 → score 80."""
    score, report = _compute_confidence(
        missing_fields=[],
        data_conflicts=["Customer CUS-1 has negative ARR: -500"],
        retrieved_at=None,
    )
    assert report["conflict_penalty"] == 20
    assert score == 80.0
    assert report["grade"] == "MEDIUM"


def test_confidence_combined_penalties():
    """3 missing fields + 1 conflict → 45 + 20 = 65 penalty → score 35 (LOW)."""
    score, report = _compute_confidence(
        missing_fields=["f1", "f2", "f3"],
        data_conflicts=["conflict_x"],
        retrieved_at=None,
    )
    assert report["completeness_penalty"] == 45
    assert report["conflict_penalty"] == 20
    assert score == 35.0
    assert report["grade"] == "CRITICAL"


def test_confidence_clamped_to_zero():
    """Enough penalties to go negative → score clamped to 0."""
    score, report = _compute_confidence(
        missing_fields=["f"] * 10,  # 10 × 15 = 150
        data_conflicts=["c"] * 5,   # 5 × 20 = 100
        retrieved_at=None,
    )
    assert score == 0.0
    assert report["grade"] == "CRITICAL"


# ── Integration tests for the evaluate_quality node ─────────────────────────

@pytest.mark.asyncio
async def test_evaluate_quality_fresh():
    """Clean data → no penalties, confidence_report in return dict."""
    state = {
        "run_id": "RUN-Q-001",
        "enterprise_state": {
            "customers": [{"customer_id": "CUS-1", "arr": 150000.0}],
            "escalations": [{"incident_id": "INC-1", "priority": "HIGH", "customer_id": "CUS-1"}],
            "specialists": [{"specialist_id": "SPEC-1", "skills": ["billing"], "capacity": 2}]
        }
    }

    with patch("app.agent.nodes.evaluate_quality.async_session") as mock_session_cls, \
         patch("app.agent.nodes.evaluate_quality.persistence") as mock_persistence:

        mock_session = MagicMock()
        mock_session_cls.return_value.__aenter__.return_value = mock_session
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session.execute = AsyncMock()
        mock_session.commit = AsyncMock()
        mock_session.begin = MagicMock()
        mock_session.begin.return_value.__aenter__ = AsyncMock(return_value=None)
        mock_session.begin.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_persistence.save_run_event = AsyncMock()

        res = await evaluate_quality(state)

    assert len(res["data_conflicts"]) == 0
    assert len(res["missing_fields"]) == 0
    assert res["source_freshness"]["crm"] == "FRESH"
    assert "confidence_report" in res
    assert res["confidence_report"]["score"] == 100.0
    assert res["confidence_report"]["grade"] == "HIGH"


@pytest.mark.asyncio
async def test_evaluate_quality_degraded_and_stale():
    """Bad data → conflicts + missing fields → degraded confidence score."""
    state = {
        "run_id": "RUN-Q-002",
        "enterprise_state": {
            "customers": [{"customer_id": "CUS-2", "arr": -1000.0}],   # conflict
            "escalations": [{"incident_id": "INC-2"}],                  # missing priority + customer_id
            "specialists": [{"specialist_id": "SPEC-2", "skills": [], "capacity": -5}]  # missing skills + conflict
        }
    }

    with patch("app.agent.nodes.evaluate_quality.async_session") as mock_session_cls, \
         patch("app.agent.nodes.evaluate_quality.persistence") as mock_persistence:

        mock_session = MagicMock()
        mock_session_cls.return_value.__aenter__.return_value = mock_session
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session.execute = AsyncMock()
        mock_session.commit = AsyncMock()
        mock_session.begin = MagicMock()
        mock_session.begin.return_value.__aenter__ = AsyncMock(return_value=None)
        mock_session.begin.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_persistence.save_run_event = AsyncMock()

        res = await evaluate_quality(state)

    # 2 conflicts (negative ARR + negative capacity)
    assert len(res["data_conflicts"]) == 2
    # 3 missing fields (priority, customer_id, skills)
    assert len(res["missing_fields"]) == 3
    # Confidence: 100 - (3×15) - (2×20) = 100 - 45 - 40 = 15
    assert res["confidence_report"]["score"] == 15.0
    assert res["confidence_report"]["grade"] == "CRITICAL"
    assert "confidence_report" in res


@pytest.mark.asyncio
async def test_evaluate_quality_emits_event():
    """Verify QUALITY_EVALUATED event is published via persistence."""
    state = {
        "run_id": "RUN-Q-003",
        "enterprise_state": {
            "customers": [],
            "escalations": [],
            "specialists": []
        }
    }

    with patch("app.agent.nodes.evaluate_quality.async_session") as mock_session_cls, \
         patch("app.agent.nodes.evaluate_quality.persistence") as mock_persistence:

        mock_session = MagicMock()
        mock_session_cls.return_value.__aenter__.return_value = mock_session
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session.execute = AsyncMock()
        mock_session.commit = AsyncMock()
        mock_session.begin = MagicMock()
        mock_session.begin.return_value.__aenter__ = AsyncMock(return_value=None)
        mock_session.begin.return_value.__aexit__ = AsyncMock(return_value=False)
        mock_persistence.save_run_event = AsyncMock()

        await evaluate_quality(state)

    mock_persistence.save_run_event.assert_called_once()
    call_kwargs = mock_persistence.save_run_event.call_args.kwargs
    assert call_kwargs["event_type"] == "QUALITY_EVALUATED"
    assert call_kwargs["run_id"] == "RUN-Q-003"
