import logging
from app.agent.state import AgentState
from app.database.session import async_session
import app.database.persistence as persistence

logger = logging.getLogger("core-api.nodes.pause_for_approval")

# ── Risk threshold constants ─────────────────────────────────────────────────
# ARR (in USD) above which a planned action is classified as HIGH risk.
_HIGH_RISK_ARR_THRESHOLD: float = 100_000.0
# Customer tiers that always trigger HIGH risk, regardless of ARR.
_HIGH_RISK_TIERS: frozenset[str] = frozenset({"gold", "platinum"})


def _assess_autonomy_risk(
    recommended_plan: dict,
    enterprise_state: dict,
) -> dict:
    """Evaluate the autonomy risk of the recommended plan.

    Risk is HIGH if any affected customer has:
    - Total ARR > _HIGH_RISK_ARR_THRESHOLD, OR
    - A tier in _HIGH_RISK_TIERS (Gold, Platinum).

    Returns a structured report dict with:
    - risk_level: 'HIGH' or 'STANDARD'
    - reasons: list of human-readable justification strings
    - affected_customers: list of {customer_id, tier, arr} dicts
    - total_arr_exposure: sum of ARR across all affected customers
    """
    allocations = (recommended_plan or {}).get("allocations", [])
    escalations = (enterprise_state or {}).get("escalations", [])
    customers = (enterprise_state or {}).get("customers", [])

    # Build fast lookup maps.
    incident_to_customer: dict[str, str] = {
        inc.get("incident_id"): inc.get("customer_id")
        for inc in escalations
        if inc.get("incident_id") and inc.get("customer_id")
    }
    customer_map: dict[str, dict] = {
        c.get("customer_id"): c
        for c in customers
        if c.get("customer_id")
    }

    # Resolve the unique set of affected customers from allocations.
    seen_customer_ids: set[str] = set()
    affected_customers: list[dict] = []
    reasons: list[str] = []
    total_arr: float = 0.0

    for alloc in allocations:
        inc_id = alloc.get("incident_id")
        cust_id = incident_to_customer.get(inc_id)
        if not cust_id or cust_id in seen_customer_ids:
            continue
        seen_customer_ids.add(cust_id)

        cust = customer_map.get(cust_id, {})
        tier = str(cust.get("tier") or "").lower()
        try:
            arr = float(cust.get("arr") or 0.0)
        except (ValueError, TypeError):
            arr = 0.0
        total_arr += arr

        affected_customers.append({
            "customer_id": cust_id,
            "tier": tier,
            "arr": arr,
        })

        # Tier-based risk reason
        if tier in _HIGH_RISK_TIERS:
            reasons.append(
                f"Approval required: plan changes active schedules for strategic "
                f"{tier.capitalize()}-tier customer {cust_id} with ${arr:,.0f} ARR exposure."
            )

        # ARR-based risk reason
        if arr > _HIGH_RISK_ARR_THRESHOLD and tier not in _HIGH_RISK_TIERS:
            reasons.append(
                f"Approval required: plan affects customer {cust_id} with high ARR exposure "
                f"of ${arr:,.0f} (threshold: ${_HIGH_RISK_ARR_THRESHOLD:,.0f})."
            )

    # Determine final risk level.
    risk_level = "HIGH" if reasons else "STANDARD"

    if risk_level == "STANDARD" and affected_customers:
        reasons.append(
            f"Plan affects {len(affected_customers)} customer(s) with total ARR "
            f"${total_arr:,.0f}. No high-risk indicators detected. Standard approval required."
        )
    elif not affected_customers:
        reasons.append("No customer data available for risk assessment. Defaulting to STANDARD.")

    return {
        "risk_level": risk_level,
        "reasons": reasons,
        "affected_customers": affected_customers,
        "total_arr_exposure": round(total_arr, 2),
        "allocation_count": len(allocations),
    }


async def pause_for_approval(state: AgentState) -> dict:
    """Graph node representing a safe pause state waiting for manager approval decision.

    Computes an autonomy risk report to explain to the manager why approval
    is required, then emits a WAITING_FOR_APPROVAL SSE event containing the
    risk justifications alongside the checkpoint.
    """
    app_status = state.get("approval_status")
    if app_status == "APPROVED":
        print("[pause_for_approval] Resuming: Approval status is APPROVED. Bypassing halt.")
        return {"status": "EXECUTING"}

    print("[pause_for_approval]\nHalting run. Waiting for manager approval...")

    run_id = state.get("run_id", "unknown")
    recommended_plan = state.get("recommended_plan") or {}
    enterprise_state = state.get("enterprise_state") or {}

    # ── Assess autonomy risk ─────────────────────────────────────────────────
    autonomy_risk_report = _assess_autonomy_risk(
        recommended_plan=recommended_plan,
        enterprise_state=enterprise_state,
    )

    logger.info(
        f"[pause_for_approval] Risk level: {autonomy_risk_report['risk_level']}. "
        f"ARR exposure: ${autonomy_risk_report['total_arr_exposure']:,.0f}. "
        f"Reasons: {len(autonomy_risk_report['reasons'])}"
    )

    checkpoint_data = dict(state)
    checkpoint_data["status"] = "WAITING_FOR_APPROVAL"
    checkpoint_data["approval_status"] = "PENDING"
    checkpoint_data["autonomy_risk_report"] = autonomy_risk_report

    async with async_session() as session:
        async with session.begin():
            await persistence.save_agent_run(
                session=session,
                run_id=run_id,
                scenario_id="phase2-demo",
                status="WAITING_FOR_APPROVAL",
                current_node="pause_for_approval"
            )
            await persistence.save_graph_checkpoint(
                session=session,
                run_id=run_id,
                state_version=1,
                node_name="pause_for_approval",
                checkpoint_json=checkpoint_data
            )
            await persistence.save_run_event(
                session=session,
                run_id=run_id,
                sequence_number=10,
                event_type="WAITING_FOR_APPROVAL",
                source="pause_for_approval",
                summary=(
                    f"Graph execution halted. Risk: {autonomy_risk_report['risk_level']}. "
                    f"Waiting for manager plan approval decision."
                ),
                payload_dict={
                    "autonomy_risk_report": autonomy_risk_report,
                    "recommended_plan_id": recommended_plan.get("plan_id"),
                },
                state_version=state.get("state_version", 1),
            )

    return {
        "approval_status": "PENDING",
        "status": "WAITING_FOR_APPROVAL",
        "autonomy_risk_report": autonomy_risk_report,
    }
