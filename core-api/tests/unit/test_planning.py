import pytest
from unittest.mock import patch
from optiflow_shared.tool_contracts import StructuredGoal, TimeHorizon
from app.goals import interpreter
from app.goals.validator import validate_goal
from app.evidence.planner import build_evidence_requirements
from app.agent.graph import compiled_graph

@pytest.mark.asyncio
async def test_example_1_renewals_and_sla():
    # Input: Protect renewals and SLA commitments
    goal_text = "Protect renewals and SLA commitments"
    
    mock_goal = StructuredGoal(
        summary="Protect renewals and SLA commitments",
        objectives=["SLA_PROTECTION", "RENEWAL_PROTECTION"],
        time_horizon=TimeHorizon(value=7, unit="DAYS"),
        hard_constraints=[],
        soft_preferences=[],
        requested_actions=[],
        ambiguities=[],
        unsupported_requests=[],
        interpretation_notes=["Mocked for testing"]
    )
    
    with patch("app.goals.interpreter.interpret_goal_text", return_value=mock_goal), \
         patch("app.agent.nodes.interpret_goal.interpret_goal_text", return_value=mock_goal):
         
        # 1. Interpret
        goal = interpreter.interpret_goal_text(goal_text)
        assert "SLA_PROTECTION" in goal.objectives
        assert "RENEWAL_PROTECTION" in goal.objectives
        
        # 2. Validate
        val_res = validate_goal(goal)
        assert val_res.valid is True
        assert val_res.clarification_required is False
        
        # 3. Evidence Planner
        reqs = build_evidence_requirements(goal)
        req_types = {r.evidence_type for r in reqs}
        
        # SLA needs: ACTIVE_ESCALATIONS, SLA_DEADLINES, etc.
        # RENEWALS needs: RENEWAL_DATE, etc.
        assert "ACTIVE_ESCALATIONS" in req_types
        assert "RENEWAL_DATE" in req_types
        
        # Run in compiled graph to check tool selection
        state = {
            "run_id": "RUN-1",
            "goal_text": goal_text,
            "status": "RECEIVED"
        }
        final_state = await compiled_graph.ainvoke(state)
        assert final_state["status"] == "WAITING_FOR_APPROVAL"
        
        selected = {t["toolName"]: t for t in final_state["selected_tools"]}
        assert selected["crm-service"]["selected"] is True
        assert selected["incident-service"]["selected"] is True
        assert selected["workforce-service"]["selected"] is True
        assert selected["communication-service"]["selected"] is False

@pytest.mark.asyncio
async def test_example_2_workload_fairly():
    # Input: Balance workload fairly
    goal_text = "Balance workload fairly for the next 7 days"
    
    mock_goal = StructuredGoal(
        summary="Balance workload fairly for the next 7 days",
        objectives=["CUSTOMER_FAIRNESS", "WORKLOAD_PROTECTION"],
        time_horizon=TimeHorizon(value=7, unit="DAYS"),
        hard_constraints=[],
        soft_preferences=[],
        requested_actions=[],
        ambiguities=[],
        unsupported_requests=[],
        interpretation_notes=["Mocked for testing"]
    )
    
    with patch("app.goals.interpreter.interpret_goal_text", return_value=mock_goal), \
         patch("app.agent.nodes.interpret_goal.interpret_goal_text", return_value=mock_goal):
         
        # 1. Interpret
        goal = interpreter.interpret_goal_text(goal_text)
        assert "CUSTOMER_FAIRNESS" in goal.objectives
        assert "WORKLOAD_PROTECTION" in goal.objectives
        
        # 2. Validate
        val_res = validate_goal(goal)
        assert val_res.valid is True
        
        # 3. Evidence Planner
        reqs = build_evidence_requirements(goal)
        req_types = {r.evidence_type for r in reqs}
        assert "CURRENT_WORKLOAD" in req_types
        assert "WAITING_TIME" in req_types
        
        # Run in graph
        state = {
            "run_id": "RUN-2",
            "goal_text": goal_text,
            "status": "RECEIVED"
        }
        final_state = await compiled_graph.ainvoke(state)
        selected = {t["toolName"]: t for t in final_state["selected_tools"]}
        
        # Workforce must be selected
        assert selected["workforce-service"]["selected"] is True
        # CRM is selected because CUSTOMER_FAIRNESS requires customer tier database access
        assert selected["crm-service"]["selected"] is True

@pytest.mark.asyncio
async def test_example_3_empty_goal():
    # Input: empty string
    goal_text = "   "
    goal = interpreter.interpret_goal_text(goal_text)
    val_res = validate_goal(goal)
    
    # Must fail validation
    assert val_res.valid is False
    assert "Goal summary cannot be empty." in val_res.blocking_reasons

@pytest.mark.asyncio
async def test_example_4_duplicate_objectives():
    # Input: SLA commitments and SLA commitments
    goal_text = "Protect SLA commitments and SLA commitments"
    
    # We bypass Gemini for this test since we are checking local deduplication logic
    mock_goal = StructuredGoal(
        summary="Protect SLA commitments and SLA commitments",
        objectives=["SLA_PROTECTION", "SLA_PROTECTION"],
        time_horizon=TimeHorizon(value=7, unit="DAYS"),
        hard_constraints=[],
        soft_preferences=[],
        requested_actions=[],
        ambiguities=[],
        unsupported_requests=[],
        interpretation_notes=["Mocked for duplicate objectives testing"]
    )
    
    with patch("app.goals.interpreter.interpret_goal_text", return_value=mock_goal):
        goal = interpreter.interpret_goal_text(goal_text)
        
        # objectives list has deduplicated after validation
        val_res = validate_goal(goal)
        assert len(goal.objectives) == 1
        assert goal.objectives == ["SLA_PROTECTION"]
        
        # Evidence list is deduplicated
        reqs = build_evidence_requirements(goal)
        req_types = [r.evidence_type for r in reqs]
        assert len(req_types) == len(set(req_types))


def test_provider_selection():
    from app.goals.providers import get_llm_provider, GeminiLLMProvider, GroqLLMProvider
    from app.config.settings import Settings
    
    mock_settings = Settings(
        database_url="sqlite+aiosqlite:///:memory:",
        crm_service_url="http://mock",
        incident_service_url="http://mock",
        workforce_service_url="http://mock",
        communication_service_url="http://mock",
        tool_shared_token="mock",
        llm_provider="gemini",
        gemini_api_key="gemini-key",
        gemini_model="gemini-3.6-flash",
        groq_api_key="groq-key",
        groq_model="llama-3.1-8b-instant"
    )
    
    # 1. Test Gemini Selection
    provider = get_llm_provider("gemini", mock_settings)
    assert isinstance(provider, GeminiLLMProvider)
    assert provider.api_key == "gemini-key"
    assert provider.model_name == "gemini-3.6-flash"
    
    # 2. Test Groq Selection
    provider = get_llm_provider("groq", mock_settings)
    assert isinstance(provider, GroqLLMProvider)
    assert provider.api_key == "groq-key"
    assert provider.model_name == "llama-3.1-8b-instant"


def test_provider_generate_text():
    from app.goals.providers import GeminiLLMProvider, GroqLLMProvider
    from unittest.mock import MagicMock, patch
    
    # 1. Test Gemini generate_text
    gemini = GeminiLLMProvider(api_key="gemini-key", model_name="gemini-3.6-flash")
    mock_response = MagicMock()
    mock_response.text = "Mocked Gemini text completion"
    
    with patch("app.goals.providers.genai.Client") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_response
        mock_client_cls.return_value = mock_client
        
        res = gemini.generate_text("Hello Gemini")
        assert res == "Mocked Gemini text completion"
        mock_client.models.generate_content.assert_called_once()
        
    # 2. Test Groq generate_text
    groq = GroqLLMProvider(api_key="groq-key", model_name="llama-3.1-8b-instant")
    mock_choice = MagicMock()
    mock_choice.message.content = "Mocked Groq text completion"
    mock_choices = [mock_choice]
    mock_completion = MagicMock()
    mock_completion.choices = mock_choices
    
    with patch("app.goals.providers.Groq") as mock_groq_cls:
        mock_groq_client = MagicMock()
        mock_groq_client.chat.completions.create.return_value = mock_completion
        mock_groq_cls.return_value = mock_groq_client
        
        res = groq.generate_text("Hello Groq")
        assert res == "Mocked Groq text completion"
        mock_groq_client.chat.completions.create.assert_called_once()


def test_provider_uses_backup_key_after_retryable_primary_failure():
    from app.goals.providers import build_llm_provider
    from unittest.mock import MagicMock, patch

    failed_client = MagicMock()
    failed_error = RuntimeError("429 quota exhausted")
    failed_error.status_code = 429
    failed_client.chat.completions.create.side_effect = failed_error

    successful_client = MagicMock()
    completion = MagicMock()
    completion.choices[0].message.content = "Backup succeeded"
    successful_client.chat.completions.create.return_value = completion

    with patch(
        "app.goals.providers.Groq",
        side_effect=[failed_client, successful_client],
    ):
        provider = build_llm_provider(
            "groq",
            "llama-3.1-8b-instant",
            ["primary-key", "backup-key"],
        )
        assert provider.generate_text("Hello") == "Backup succeeded"


def test_provider_does_not_retry_nonrecoverable_response_error():
    from app.goals.providers import build_llm_provider
    from unittest.mock import MagicMock, patch
    import pytest

    failed_client = MagicMock()
    failed_client.chat.completions.create.side_effect = ValueError(
        "Malformed response"
    )

    with patch("app.goals.providers.Groq", return_value=failed_client) as client:
        provider = build_llm_provider(
            "groq",
            "llama-3.1-8b-instant",
            ["primary-key", "backup-key"],
        )
        with pytest.raises(RuntimeError, match="All eligible"):
            provider.generate_text("Hello")
        assert client.call_count == 1
        assert failed_client.chat.completions.create.call_count == 1

