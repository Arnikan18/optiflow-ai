import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from app.agent.nodes.pause_for_approval import pause_for_approval, _assess_autonomy_risk

def test_assess_autonomy_risk_standard():
    # Simple customer and allocation that doesn't breach the thresholds
    recommended_plan = {
        "plan_id": "PLAN-BALANCED",
        "allocations": [{"incident_id": "INC-1", "specialist_id": "SPEC-1"}]
    }
    enterprise_state = {
        "customers": [{"customer_id": "CUS-1", "tier": "silver", "arr": 50000.0}],
        "escalations": [{"incident_id": "INC-1", "customer_id": "CUS-1"}],
        "specialists": []
    }
    report = _assess_autonomy_risk(recommended_plan, enterprise_state)
    assert report["risk_level"] == "STANDARD"
    assert report["total_arr_exposure"] == 50000.0
    assert any("Standard approval required" in r for r in report["reasons"])

def test_assess_autonomy_risk_high_arr():
    recommended_plan = {
        "plan_id": "PLAN-BALANCED",
        "allocations": [{"incident_id": "INC-1", "specialist_id": "SPEC-1"}]
    }
    enterprise_state = {
        "customers": [{"customer_id": "CUS-1", "tier": "silver", "arr": 150000.0}],
        "escalations": [{"incident_id": "INC-1", "customer_id": "CUS-1"}],
        "specialists": []
    }
    report = _assess_autonomy_risk(recommended_plan, enterprise_state)
    assert report["risk_level"] == "HIGH"
    assert report["total_arr_exposure"] == 150000.0
    assert any("high ARR exposure" in r for r in report["reasons"])

def test_assess_autonomy_risk_gold_tier():
    recommended_plan = {
        "plan_id": "PLAN-BALANCED",
        "allocations": [{"incident_id": "INC-1", "specialist_id": "SPEC-1"}]
    }
    enterprise_state = {
        "customers": [{"customer_id": "CUS-1", "tier": "gold", "arr": 10000.0}],
        "escalations": [{"incident_id": "INC-1", "customer_id": "CUS-1"}],
        "specialists": []
    }
    report = _assess_autonomy_risk(recommended_plan, enterprise_state)
    assert report["risk_level"] == "HIGH"
    assert report["total_arr_exposure"] == 10000.0
    assert any("strategic Gold-tier customer" in r for r in report["reasons"])

@pytest.mark.asyncio
async def test_pause_for_approval_approved():
    state = {
        "run_id": "RUN-TEST-001",
        "approval_status": "APPROVED",
        "status": "WAITING_FOR_APPROVAL"
    }
    res = await pause_for_approval(state)
    assert res == {"status": "EXECUTING"}

@pytest.mark.asyncio
async def test_pause_for_approval_halt():
    state = {
        "run_id": "RUN-TEST-002",
        "approval_status": "PENDING",
        "status": "WAITING_FOR_APPROVAL",
        "recommended_plan": {
            "plan_id": "PLAN-BALANCED",
            "allocations": [{"incident_id": "INC-1", "specialist_id": "SPEC-1"}]
        },
        "enterprise_state": {
            "customers": [{"customer_id": "CUS-1", "tier": "gold", "arr": 10000.0}],
            "escalations": [{"incident_id": "INC-1", "customer_id": "CUS-1"}],
            "specialists": []
        }
    }

    with patch("app.agent.nodes.pause_for_approval.async_session") as mock_session_cls, \
         patch("app.agent.nodes.pause_for_approval.persistence") as mock_persistence:

        mock_session = MagicMock()
        mock_session_cls.return_value.__aenter__.return_value = mock_session
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)
        mock_session.begin = MagicMock()
        mock_session.begin.return_value.__aenter__ = AsyncMock(return_value=None)
        mock_session.begin.return_value.__aexit__ = AsyncMock(return_value=False)

        mock_persistence.save_agent_run = AsyncMock()
        mock_persistence.save_graph_checkpoint = AsyncMock()
        mock_persistence.save_run_event = AsyncMock()

        res = await pause_for_approval(state)
        
        assert res["approval_status"] == "PENDING"
        assert res["status"] == "WAITING_FOR_APPROVAL"
        assert res["autonomy_risk_report"]["risk_level"] == "HIGH"
        
        mock_persistence.save_agent_run.assert_called_once()
        mock_persistence.save_graph_checkpoint.assert_called_once()
        mock_persistence.save_run_event.assert_called_once()
