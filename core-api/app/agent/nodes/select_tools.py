from app.agent.state import AgentState
from app.evidence.registry import EvidenceRegistry
from app.database.session import async_session
import app.database.persistence as persistence
from optiflow_shared.enums import EvidenceType, ToolService

# Human-readable business justifications for each service when selected.
_SELECTION_REASONS: dict[str, str] = {
    ToolService.CRM.value: (
        "CRM selected because commercial customer data "
        "(ARR, renewal dates, or tier information) is required."
    ),
    ToolService.INCIDENT.value: (
        "Incident service selected because active escalation or "
        "SLA deadline data is required."
    ),
    ToolService.WORKFORCE.value: (
        "Workforce service selected because specialist availability, "
        "capacity, or workload data is required."
    ),
    ToolService.COMMUNICATION.value: (
        "Communication service selected because assignment response "
        "or notification status data is required."
    ),
}

# Human-readable business justifications for each service when skipped.
_SKIP_REASONS: dict[str, str] = {
    ToolService.CRM.value: (
        "CRM skipped – no commercial, renewal, or customer-tier "
        "evidence is required for this goal."
    ),
    ToolService.INCIDENT.value: (
        "Incident service skipped – no active escalation or SLA "
        "data is required for this goal."
    ),
    ToolService.WORKFORCE.value: (
        "Workforce service skipped – no specialist availability or "
        "workload data is required for this goal."
    ),
    ToolService.COMMUNICATION.value: (
        "Communication service skipped until execution "
        "(write-only notification channel, not needed during planning)."
    ),
}


async def select_tools(state: AgentState) -> dict:
    """Agent node responsible for selecting/skipping mock services.

    Inspects required evidence types, looks up service ownership, and determines
    which tool-services must be invoked in the next phase. Publishes a
    TOOLS_SELECTED SSE event so the frontend can display the tool selection
    reasoning in the decision timeline.
    """
    print("[select_tools]\nTools selected")

    run_id = state.get("run_id", "unknown")
    reqs_list = state.get("evidence_requirements", [])
    required_evidence_types = {r["evidence_type"] for r in reqs_list}

    registry = EvidenceRegistry()

    services = [
        ToolService.CRM,
        ToolService.INCIDENT,
        ToolService.WORKFORCE,
        ToolService.COMMUNICATION,
    ]
    selected_tools = []

    for srv in services:
        needed_evidence = []
        for et_str in required_evidence_types:
            try:
                et = EvidenceType(et_str)
                auth_srv = registry.get_authoritative_tool(et)
                if auth_srv == srv:
                    needed_evidence.append(et_str)
            except ValueError:
                pass

        if needed_evidence:
            selected_tools.append({
                "toolName": srv.value,
                "selected": True,
                "reason": _SELECTION_REASONS.get(srv.value, f"Required evidence: {', '.join(needed_evidence)}"),
                "requestedEvidence": needed_evidence,
            })
        else:
            selected_tools.append({
                "toolName": srv.value,
                "selected": False,
                "reason": _SKIP_REASONS.get(srv.value, "Not required for this goal."),
                "requestedEvidence": [],
            })

    # Publish TOOLS_SELECTED SSE event so the frontend decision timeline can
    # display which services were chosen and why.
    async with async_session() as session:
        async with session.begin():
            await persistence.save_run_event(
                session=session,
                run_id=run_id,
                sequence_number=3,
                event_type="TOOLS_SELECTED",
                source="select_tools",
                summary=(
                    f"{sum(1 for t in selected_tools if t['selected'])} service(s) selected, "
                    f"{sum(1 for t in selected_tools if not t['selected'])} skipped"
                ),
                payload_dict={"tools": selected_tools},
                state_version=state.get("state_version", 1),
            )

    return {"selected_tools": selected_tools}
