import pytest
from unittest.mock import patch, MagicMock
from app.agent.nodes.evaluate_quality import evaluate_quality

@pytest.mark.asyncio
async def test_evaluate_quality_fresh():
    state = {
        "run_id": "RUN-Q-001",
        "enterprise_state": {
            "customers": [{"customer_id": "CUS-1", "arr": 150000.0}],
            "escalations": [{"incident_id": "INC-1", "priority": "HIGH", "customer_id": "CUS-1"}],
            "specialists": [{"specialist_id": "SPEC-1", "skills": ["billing"], "capacity": 2}]
        }
    }
    
    with patch("app.agent.nodes.evaluate_quality.async_session") as mock_session_cls:
        mock_session = MagicMock()
        mock_session_cls.return_value.__aenter__.return_value = mock_session
        
        from unittest.mock import AsyncMock
        mock_session.execute = AsyncMock()
        
        res = await evaluate_quality(state)
        assert len(res["data_conflicts"]) == 0
        assert len(res["missing_fields"]) == 0
        assert res["source_freshness"]["crm"] == "FRESH"
        mock_session.execute.assert_called_once()

@pytest.mark.asyncio
async def test_evaluate_quality_degraded_and_stale():
    state = {
        "run_id": "RUN-Q-002",
        "enterprise_state": {
            "customers": [{"customer_id": "CUS-2", "arr": -1000.0}], # Negative ARR conflict
            "escalations": [{"incident_id": "INC-2"}], # Missing priority and customer_id
            "specialists": [{"specialist_id": "SPEC-2", "skills": [], "capacity": -5}] # Empty skills & negative capacity
        }
    }
    
    with patch("app.agent.nodes.evaluate_quality.async_session") as mock_session_cls:
        mock_session = MagicMock()
        mock_session_cls.return_value.__aenter__.return_value = mock_session
        from unittest.mock import AsyncMock
        mock_session.execute = AsyncMock()
        
        res = await evaluate_quality(state)
        # Should catch negative ARR and negative capacity
        assert len(res["data_conflicts"]) == 2
        # Should catch missing priority, customer_id, and skills
        assert len(res["missing_fields"]) == 3
        mock_session.execute.assert_called_once()
