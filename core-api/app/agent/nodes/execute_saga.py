import logging
import asyncio
from app.agent.state import AgentState
from app.adapters.tool_client import ToolClient
from app.database.session import async_session
from app.config.settings import settings
import app.database.persistence as persistence

logger = logging.getLogger("core-api.nodes.execute_saga")

# Polling bounds — configurable via SAGA_POLL_MAX_ATTEMPTS / SAGA_POLL_INTERVAL_SECONDS env vars.
_POLL_MAX_ATTEMPTS: int = settings.saga_poll_max_attempts
_POLL_INTERVAL_SECONDS: float = settings.saga_poll_interval_seconds



async def _poll_assignment_status(
    client: ToolClient,
    request_id: str,
    run_id: str,
    session,
) -> str:
    """Polls the communication service for a specialist's response.

    Returns one of: 'ACCEPTED', 'REJECTED', 'TIMEOUT'.
    Publishes SPECIALIST_POLLING events on each attempt.
    """
    for attempt in range(1, _POLL_MAX_ATTEMPTS + 1):
        await persistence.save_run_event(
            session=session,
            run_id=run_id,
            sequence_number=50 + attempt,
            event_type="SPECIALIST_POLLING",
            source="execute_saga",
            summary=f"Polling specialist response for request {request_id} (attempt {attempt}/{_POLL_MAX_ATTEMPTS})",
            payload_dict={"request_id": request_id, "attempt": attempt},
            state_version=1,
        )

        try:
            data = await client.get_assignment_request(request_id=request_id)
            response_status = (data or {}).get("status", "PENDING")

            if response_status == "ACCEPTED":
                return "ACCEPTED"
            elif response_status == "REJECTED":
                return "REJECTED"
            # PENDING / unknown – keep polling
        except Exception as poll_err:
            logger.warning(f"Poll attempt {attempt} failed for {request_id}: {poll_err}")

        if attempt < _POLL_MAX_ATTEMPTS:
            await asyncio.sleep(_POLL_INTERVAL_SECONDS)

    return "TIMEOUT"


async def execute_saga(state: AgentState) -> dict:
    """Graph node managing the transactional SAGA writes back to microservices.

    Execution order per allocation:
      A. Create a TENTATIVE workforce reservation (not yet confirmed).
      B. Dispatch the communication assignment request to notify the specialist.
      C. Poll for the specialist's response (ACCEPTED / REJECTED / TIMEOUT).
         - ACCEPTED  → confirm reservation, then assign the incident.
         - REJECTED  → cancel reservation, record the excluded pair, set REPLANNING.
         - TIMEOUT   → cancel reservation, record the excluded pair, set REPLANNING.

    A REPLANNING status signals to the LangGraph router (Task 2.2) that the
    workflow must loop back to re-plan with the excluded pairs as constraints.
    """
    print("[execute_saga]\nExecuting tentative reservation locks, assignments, and alerts...")

    run_id = state.get("run_id", "unknown")
    recommended = state.get("recommended_plan") or {}
    allocations = recommended.get("allocations", [])

    # Carry forward the replan counter and any excluded pairs from previous loops.
    current_replan_count: int = int(state.get("replan_count") or 0)
    excluded_pairs: list = list(state.get("excluded_specialist_incidents", []) or [])

    client = ToolClient(request_id=run_id)

    created_reservations: list = []
    updated_incidents: list = []
    execution_actions: list = []
    execution_receipts: list = []

    saga_failed = False
    needs_replan = False
    failure_reason = ""

    for alloc in allocations:
        inc_id = alloc.get("incident_id")
        spec_id = alloc.get("specialist_id")

        if not inc_id or not spec_id:
            continue

        res_id = f"RES-{run_id[:8]}-{inc_id[:8]}"
        req_id = f"REQ-{run_id[:8]}-{inc_id[:8]}"

        try:
            # ── STEP A: Tentative workforce reservation ──────────────────────
            print(f"  [SAGA] Creating tentative reservation {res_id} for specialist {spec_id} on incident {inc_id}...")
            async with async_session() as session:
                async with session.begin():
                    await client.create_reservation(
                        reservation_id=res_id,
                        specialist_id=spec_id,
                        incident_id=inc_id,
                        expires_in_seconds=300,
                    )
                    created_reservations.append(res_id)
                    execution_actions.append(
                        {"action": "RESERVE_TENTATIVE", "entity": "workforce-service", "id": res_id}
                    )
                    await persistence.save_run_event(
                        session=session,
                        run_id=run_id,
                        sequence_number=48,
                        event_type="SAGA_EXECUTING",
                        source="execute_saga",
                        summary=f"Tentative reservation {res_id} created for {spec_id} on {inc_id}",
                        payload_dict={"reservation_id": res_id, "specialist_id": spec_id, "incident_id": inc_id},
                        state_version=1,
                    )

            # ── STEP B: Dispatch communication assignment request ────────────
            print(f"  [SAGA] Dispatching assignment request {req_id} to specialist {spec_id}...")
            await client.create_assignment_request(
                request_id=req_id,
                incident_id=inc_id,
                specialist_id=spec_id,
                message=f"OptiFlow Assignment: Please review SLA Escalation {inc_id} immediately.",
                expires_in_seconds=300,
            )
            execution_actions.append(
                {"action": "CREATE_NOTIFICATION", "entity": "communication-service", "id": req_id}
            )

            # ── STEP C: Poll for specialist response ─────────────────────────
            print(f"  [SAGA] Polling specialist response for request {req_id}...")
            async with async_session() as session:
                async with session.begin():
                    poll_result = await _poll_assignment_status(
                        client=client,
                        request_id=req_id,
                        run_id=run_id,
                        session=session,
                    )

            if poll_result == "ACCEPTED":
                # ── STEP D: Confirm reservation and assign incident ──────────
                print(f"  [SAGA] Specialist ACCEPTED {req_id}. Confirming reservation {res_id}...")
                await client.confirm_reservation(reservation_id=res_id)
                await client.assign_incident_specialist(incident_id=inc_id, specialist_id=spec_id)
                await client.patch_incident_status(incident_id=inc_id, incident_status="ASSIGNED")
                updated_incidents.append(inc_id)
                execution_actions.append(
                    {"action": "RESERVE_CONFIRM", "entity": "workforce-service", "id": res_id}
                )
                execution_actions.append(
                    {"action": "ASSIGN_INCIDENT", "entity": "incident-service", "id": inc_id}
                )
                execution_receipts.append({
                    "receipt_id": f"REC-{run_id[:8]}-{inc_id[:8]}",
                    "allocation": alloc,
                    "status": "SUCCESS",
                    "actions": ["RESERVE_TENTATIVE", "NOTIFY", "SPECIALIST_ACCEPTED", "RESERVE_CONFIRM", "ASSIGN"],
                })

                async with async_session() as session:
                    async with session.begin():
                        await persistence.save_run_event(
                            session=session,
                            run_id=run_id,
                            sequence_number=56,
                            event_type="SPECIALIST_ACCEPTED",
                            source="execute_saga",
                            summary=f"Specialist {spec_id} accepted assignment for incident {inc_id}",
                            payload_dict={"specialist_id": spec_id, "incident_id": inc_id, "reservation_id": res_id},
                            state_version=1,
                        )

            else:
                # REJECTED or TIMEOUT ─ compensate and flag for replanning ───
                reason_label = "REJECTED" if poll_result == "REJECTED" else "TIMED OUT"
                print(f"  [SAGA] Specialist {reason_label} request {req_id}. Cancelling reservation {res_id}...")

                try:
                    await client.cancel_reservation(reservation_id=res_id)
                    created_reservations.remove(res_id)
                except Exception as cancel_err:
                    logger.warning(f"Reservation cancel after {reason_label} failed for {res_id}: {cancel_err}")

                excluded_pairs.append({"specialist_id": spec_id, "incident_id": inc_id})
                needs_replan = True

                execution_receipts.append({
                    "receipt_id": f"REC-{run_id[:8]}-{inc_id[:8]}",
                    "allocation": alloc,
                    "status": poll_result,
                    "actions": ["RESERVE_TENTATIVE", "NOTIFY", f"SPECIALIST_{poll_result}", "RESERVE_CANCELLED"],
                })

                async with async_session() as session:
                    async with session.begin():
                        await persistence.save_run_event(
                            session=session,
                            run_id=run_id,
                            sequence_number=57,
                            event_type="SPECIALIST_REJECTED",
                            source="execute_saga",
                            summary=f"Specialist {spec_id} {reason_label.lower()} request for incident {inc_id}. Replanning required.",
                            payload_dict={
                                "specialist_id": spec_id,
                                "incident_id": inc_id,
                                "poll_result": poll_result,
                                "excluded_pairs": excluded_pairs,
                            },
                            state_version=1,
                        )
                # Stop processing further allocations; trigger a full replan.
                break

        except Exception as e:
            logger.warning(f"Saga execution failed for allocation {alloc}: {str(e)}")
            saga_failed = True
            failure_reason = f"Failure on ticket allocation {inc_id}: {str(e)}"
            break

    # ── SAGA Rollback for unexpected service errors ──────────────────────────
    if saga_failed:
        print(f"\n[SAGA ROLLBACK] Triggering compensation workflows due to: {failure_reason}")

        for r_id in created_reservations:
            try:
                print(f"  [ROLLBACK] Cancelling reservation {r_id}...")
                await client.cancel_reservation(reservation_id=r_id)
            except Exception as re:
                logger.error(f"Saga compensating reservation cancel failed for {r_id}: {str(re)}")

        for i_id in updated_incidents:
            try:
                print(f"  [ROLLBACK] Resetting incident {i_id} to UNASSIGNED...")
                await client.assign_incident_specialist(incident_id=i_id, specialist_id="")
                await client.patch_incident_status(incident_id=i_id, incident_status="OPEN")
            except Exception as ie:
                logger.error(f"Saga compensating incident reset failed for {i_id}: {str(ie)}")

    # ── Determine final status ───────────────────────────────────────────────
    if needs_replan:
        status_outcome = "REPLANNING"
    elif saga_failed:
        status_outcome = "FAILED_SAGA"
    else:
        status_outcome = "EXECUTED"

    # ── Persist SAGA outcome ─────────────────────────────────────────────────
    async with async_session() as session:
        async with session.begin():
            await persistence.save_agent_run(
                session=session,
                run_id=run_id,
                scenario_id="phase2-demo",
                status=status_outcome,
                current_node="execute_saga",
            )
            await persistence.save_run_event(
                session=session,
                run_id=run_id,
                sequence_number=60,
                event_type="SAGA_COMPLETED" if status_outcome == "EXECUTED" else "SAGA_FAILED",
                source="execute_saga",
                summary=f"Saga execution resolved: {status_outcome}. {failure_reason}",
                payload_dict={
                    "receipts": execution_receipts,
                    "actions_attempted": execution_actions,
                    "excluded_pairs": excluded_pairs,
                },
                state_version=1,
            )

    # Increment replan_count only when this execution triggered a replanning loop.
    # generate_plans reads this value and evaluates the max_replan_count guard
    # before running CP-SAT, so incrementing here ensures the guard is
    # evaluated against the correct count on the very next planning cycle.
    next_replan_count = (current_replan_count + 1) if needs_replan else current_replan_count

    return {
        "execution_actions": execution_actions,
        "execution_receipts": execution_receipts,
        "excluded_specialist_incidents": excluded_pairs,
        "status": status_outcome,
        "replan_count": next_replan_count,
    }
