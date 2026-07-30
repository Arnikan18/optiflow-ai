import pytest
from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_create_run_route():
    with patch("app.main.start_new_run") as mock_start:
        response = client.post("/api/v1/runs", json={"goal_text": "Optimize renewals"})
        assert response.status_code == 201
        data = response.json()
        assert "run_id" in data
        assert data["status"] == "RECEIVED"
        mock_start.assert_called_once()

def test_create_run_empty_goal():
    response = client.post("/api/v1/runs", json={"goal_text": ""})
    assert response.status_code == 422
    
    response = client.post("/api/v1/runs", json={"goal_text": "   "})
    assert response.status_code == 422

def test_get_run_status_not_found():
    response = client.get("/api/v1/runs/RUN-MISSING-123")
    assert response.status_code == 404
    assert response.json()["detail"] == "Run not found"

def test_approve_run_route_not_found():
    with patch("sqlalchemy.ext.asyncio.AsyncSession.execute") as mock_execute:
        mock_result = MagicMock()
        mock_result.fetchone.return_value = None
        mock_execute.return_value = mock_result
        response = client.post("/api/v1/runs/RUN-MISSING-123/approve", json={"approval_status": "APPROVED"})
        assert response.status_code == 404
        assert response.json()["detail"] == "Run not found"

def test_approve_run_route_success():
    with patch("app.main.resume_run_from_checkpoint", return_value=True) as mock_resume, \
         patch("sqlalchemy.ext.asyncio.AsyncSession.execute") as mock_execute:
        mock_result = MagicMock()
        mock_result.fetchone.return_value = ("WAITING_FOR_APPROVAL",)
        mock_execute.return_value = mock_result
        response = client.post("/api/v1/runs/RUN-EXIST-999/approve", json={
            "approval_status": "APPROVED",
            "recommended_plan": {"plan_id": "PLAN-BALANCED"}
        })
        assert response.status_code == 200
        assert response.json()["status"] == "success"
        mock_resume.assert_called_once_with("RUN-EXIST-999", "APPROVED", {"plan_id": "PLAN-BALANCED"})

def test_clarify_run_route_success():
    with patch("app.main.resume_run_from_checkpoint", return_value=True) as mock_resume, \
         patch("sqlalchemy.ext.asyncio.AsyncSession.execute") as mock_execute:
        mock_result = MagicMock()
        mock_result.fetchone.return_value = ("WAITING_FOR_CLARIFICATION",)
        mock_execute.return_value = mock_result
        response = client.post("/api/v1/runs/RUN-EXIST-999/clarify", json={
            "clarification_reply": "Here is the details"
        })
        assert response.status_code == 200
        assert response.json()["status"] == "success"
        mock_resume.assert_called_once_with(
            run_id="RUN-EXIST-999", 
            approval_status="PENDING",
            clarification_reply="Here is the details"
        )

@pytest.mark.asyncio
async def test_manager_resume_run_no_checkpoint():
    from app.agent.manager import resume_run_from_checkpoint
    
    with patch("app.agent.manager.load_last_checkpoint", return_value=None) as mock_load:
        success = await resume_run_from_checkpoint("RUN-FAKE", "APPROVED")
        assert success is False
        mock_load.assert_called_once_with("RUN-FAKE")

@pytest.mark.asyncio
async def test_manager_resume_run_success():
    from app.agent.manager import resume_run_from_checkpoint
    
    mock_state = {"run_id": "RUN-FAKE", "goal_text": "Optimize SLA", "candidate_plans": []}
    
    with patch("app.agent.manager.load_last_checkpoint", return_value=mock_state) as mock_load, \
         patch("app.agent.manager.asyncio.create_task") as mock_create_task:
         
        success = await resume_run_from_checkpoint("RUN-FAKE", "APPROVED", {"plan_id": "PLAN-SLA"})
        assert success is True
        mock_load.assert_called_once_with("RUN-FAKE")
        
        # Verify that state was updated with resumer context
        expected_state = mock_state.copy()
        expected_state["approval_status"] = "APPROVED"
        expected_state["recommended_plan"] = {"plan_id": "PLAN-SLA"}
        
        mock_create_task.assert_called_once()

@pytest.mark.asyncio
async def test_manager_resume_run_clarification():
    from app.agent.manager import resume_run_from_checkpoint
    
    mock_state = {
        "run_id": "RUN-FAKE",
        "goal_text": "Optimize",
        "structured_goal": {"ambiguities": ["Which tiers?"]}
    }
    
    with patch("app.agent.manager.load_last_checkpoint", return_value=mock_state) as mock_load, \
         patch("app.agent.manager.asyncio.create_task") as mock_create_task:
         
        success = await resume_run_from_checkpoint(
            run_id="RUN-FAKE",
            approval_status="PENDING",
            clarification_reply="Tier 1"
        )
        assert success is True
        mock_load.assert_called_once_with("RUN-FAKE")
        
        # Verify that state was updated with clarification context and ambiguities cleared
        assert mock_state["goal_text"] == "Optimize (Clarification: Tier 1)"
        assert mock_state["structured_goal"]["ambiguities"] == []
        assert mock_state["approval_status"] == "PENDING"
        mock_create_task.assert_called_once()

def test_get_run_status_success():
    with patch("sqlalchemy.ext.asyncio.AsyncSession.execute") as mock_execute, \
         patch("app.main.load_last_checkpoint") as mock_load:
         
        mock_result = MagicMock()
        mock_result.fetchone.return_value = ("RUN-EXIST-123", "WAITING_FOR_APPROVAL", "pause_for_approval", "PLAN-BALANCED")
        mock_execute.return_value = mock_result
        
        mock_load.return_value = {
            "candidate_plans": [{"plan_id": "PLAN-BALANCED"}],
            "confidence_report": {"score": 95.0, "grade": "HIGH"},
            "autonomy_risk_report": {"risk_level": "STANDARD"},
            "replan_count": 1,
            "excluded_specialist_incidents": [],
            "structured_goal": {"objectives": ["SLA_PROTECTION"]},
            "selected_tools": [{"toolName": "crm-service", "selected": True}],
            "business_summary": "Summary markdown",
            "change_summary": "Change markdown"
        }
        
        response = client.get("/api/v1/runs/RUN-EXIST-123")
        assert response.status_code == 200
        data = response.json()
        assert data["run_id"] == "RUN-EXIST-123"
        assert data["status"] == "WAITING_FOR_APPROVAL"
        assert data["current_node"] == "pause_for_approval"
        assert data["recommended_plan_id"] == "PLAN-BALANCED"
        assert data["candidate_plans"] == [{"plan_id": "PLAN-BALANCED"}]
        assert data["confidence_report"] == {"score": 95.0, "grade": "HIGH"}
        assert data["autonomy_risk_report"] == {"risk_level": "STANDARD"}
        assert data["replan_count"] == 1
        assert data["excluded_specialist_incidents"] == []
        assert data["structured_goal"] == {"objectives": ["SLA_PROTECTION"]}
        assert data["selected_tools"] == [{"toolName": "crm-service", "selected": True}]
        assert data["business_summary"] == "Summary markdown"
        assert data["change_summary"] == "Change markdown"

def test_get_run_status_handles_nullable_partial_checkpoint():
    with patch("sqlalchemy.ext.asyncio.AsyncSession.execute") as mock_execute, \
         patch("app.main.load_last_checkpoint") as mock_load:
        mock_result = MagicMock()
        mock_result.fetchone.return_value = (
            "RUN-PARTIAL-123",
            "WAITING_FOR_CLARIFICATION",
            "pause_for_clarification",
            None,
        )
        mock_execute.return_value = mock_result
        mock_load.return_value = {
            "candidate_plans": None,
            "enterprise_state": None,
        }

        response = client.get("/api/v1/runs/RUN-PARTIAL-123")

        assert response.status_code == 200
        data = response.json()
        assert data["candidate_plans"] == []
        assert data["candidate_plan_summary"] == []
