import logging
from datetime import datetime, timezone
from sqlalchemy import text
from app.agent.state import AgentState
from app.database.session import async_session
import app.database.persistence as persistence

logger = logging.getLogger("core-api.nodes.evaluate_quality")

# ── Penalty constants (roadmap specification) ────────────────────────────────
# Freshness: -10 per hour a record is older than its policy threshold.
_FRESHNESS_PENALTY_PER_HOUR = 10
# Completeness: -15 per missing non-critical field.
_COMPLETENESS_PENALTY_PER_FIELD = 15
# Conflict: -20 per contradictory record.
_CONFLICT_PENALTY_PER_ITEM = 20

# Source freshness age thresholds (seconds). Mirrors EvidenceRegistry TTLs.
_FRESHNESS_THRESHOLDS: dict[str, int] = {
    "crm": 86400,       # 24 h
    "incident": 120,    # 2 min
    "workforce": 60,    # 1 min
    "communication": 30,
}


def _compute_confidence(
    missing_fields: list[str],
    data_conflicts: list[str],
    retrieved_at: str | None,
) -> tuple[float, dict]:
    """Compute deterministic confidence score and return the breakdown report.

    Formula (roadmap §Task 2.3):
        confidence = 100 - sum(freshness_penalties)
                         - sum(completeness_penalties)
                         - sum(conflict_penalties)

    Clamped to [0, 100].
    """
    completeness_penalty = len(missing_fields) * _COMPLETENESS_PENALTY_PER_FIELD
    conflict_penalty = len(data_conflicts) * _CONFLICT_PENALTY_PER_ITEM

    # Freshness penalty: compute age from retrieved_at (ISO UTC string).
    freshness_penalty = 0
    freshness_age_hours: float = 0.0
    if retrieved_at:
        try:
            retrieved_dt = datetime.fromisoformat(retrieved_at).replace(tzinfo=timezone.utc)
            age_seconds = (datetime.now(timezone.utc) - retrieved_dt).total_seconds()
            # Apply the longest (most lenient) threshold — crm — as the general policy.
            threshold_seconds = _FRESHNESS_THRESHOLDS["crm"]
            if age_seconds > threshold_seconds:
                hours_over = (age_seconds - threshold_seconds) / 3600.0
                freshness_penalty = int(hours_over * _FRESHNESS_PENALTY_PER_HOUR)
                freshness_age_hours = round(age_seconds / 3600, 2)
        except (ValueError, TypeError):
            pass

    total_penalty = freshness_penalty + completeness_penalty + conflict_penalty
    score = max(0.0, min(100.0, 100.0 - total_penalty))

    report = {
        "score": round(score, 1),
        "freshness_penalty": freshness_penalty,
        "completeness_penalty": completeness_penalty,
        "conflict_penalty": conflict_penalty,
        "total_penalty": total_penalty,
        "freshness_age_hours": freshness_age_hours,
        "missing_field_count": len(missing_fields),
        "conflict_count": len(data_conflicts),
        "grade": _grade(score),
    }
    return score, report


def _grade(score: float) -> str:
    """Map numeric score to a human-readable quality grade."""
    if score >= 90:
        return "HIGH"
    elif score >= 70:
        return "MEDIUM"
    elif score >= 50:
        return "LOW"
    return "CRITICAL"


async def evaluate_quality(state: AgentState) -> dict:
    """Graph node checking evidence completeness, freshness and conflicts.

    Computes a deterministic confidence score using the roadmap formula:
        confidence = 100 - freshness_penalties - completeness_penalties - conflict_penalties

    Saves the report to state['confidence_report'] and publishes a
    QUALITY_EVALUATED SSE event.
    """
    print("[evaluate_quality]\nVerifying evidence quality and resolving database references...")
    
    ent_state = state.get("enterprise_state") or {}
    run_id = state.get("run_id", "unknown")
    
    customers = ent_state.get("customers", [])
    escalations = ent_state.get("escalations", [])
    specialists = ent_state.get("specialists", [])
    
    # Retrieve the snapshot timestamp if available (set by build_state).
    snapshot_retrieved_at: str | None = ent_state.get("retrieved_at")
    
    missing_fields: list[str] = []
    data_conflicts: list[str] = []
    source_freshness = {
        "crm": "FRESH",
        "incident": "FRESH",
        "workforce": "FRESH",
        "communication": "FRESH"
    }
    
    # ── 1. Validate customer data integrity ──────────────────────────────────
    for c in customers:
        c_id = c.get("customer_id")
        if not c_id:
            missing_fields.append("Customer missing customer_id")
            continue
        try:
            arr = float(c.get("arr") or 0.0)
        except (ValueError, TypeError):
            arr = 0.0
        if arr < 0:
            data_conflicts.append(f"Customer {c_id} has negative ARR: {arr}")
            
    # ── 2. Validate incident data integrity ──────────────────────────────────
    for esc in escalations:
        inc_id = esc.get("incident_id")
        if not inc_id:
            missing_fields.append("Escalation missing incident_id")
            continue
        if not esc.get("priority"):
            missing_fields.append(f"Escalation {inc_id} missing priority")
        if not esc.get("customer_id"):
            missing_fields.append(f"Escalation {inc_id} missing customer_id")
            
    # ── 3. Validate specialist data integrity ────────────────────────────────
    for s in specialists:
        spec_id = s.get("specialist_id")
        if not spec_id:
            missing_fields.append("Specialist missing specialist_id")
            continue
        if not s.get("skills"):
            missing_fields.append(f"Specialist {spec_id} has empty or missing skills")
        cap = s.get("capacity", 0)
        if cap < 0:
            data_conflicts.append(f"Specialist {spec_id} has negative capacity: {cap}")
            
    # ── 4. Compute confidence score ──────────────────────────────────────────
    confidence_score, confidence_report = _compute_confidence(
        missing_fields=missing_fields,
        data_conflicts=data_conflicts,
        retrieved_at=snapshot_retrieved_at,
    )

    # Derive overall quality status from score grade.
    grade = confidence_report["grade"]
    quality_status_map = {"HIGH": "FRESH", "MEDIUM": "FRESH", "LOW": "DEGRADED", "CRITICAL": "STALE"}
    quality_status = quality_status_map.get(grade, "DEGRADED")
    # Legacy fallback: always use STALE if explicit data conflicts exist.
    if data_conflicts:
        quality_status = "STALE"
    elif missing_fields:
        quality_status = "DEGRADED"

    logger.info(
        f"Quality evaluation complete. Score: {confidence_score} ({grade}). "
        f"Conflicts: {len(data_conflicts)} | Missing: {len(missing_fields)}"
    )

    # ── 5. Persist quality status and publish QUALITY_EVALUATED event ────────
    async with async_session() as session:
        try:
            await session.execute(
                text("UPDATE state_snapshots SET quality_category = :q WHERE run_id = :r"),
                {"q": quality_status, "r": run_id}
            )
            await session.commit()
        except Exception as e:
            logger.warning(f"Failed to update state snapshot quality in database: {str(e)}")

        async with session.begin():
            await persistence.save_run_event(
                session=session,
                run_id=run_id,
                sequence_number=6,
                event_type="QUALITY_EVALUATED",
                source="evaluate_quality",
                summary=(
                    f"Confidence score: {confidence_score}/100 ({grade}). "
                    f"{len(missing_fields)} missing field(s), {len(data_conflicts)} conflict(s)."
                ),
                payload_dict={
                    "confidence_report": confidence_report,
                    "source_freshness": source_freshness,
                    "missing_fields": missing_fields,
                    "data_conflicts": data_conflicts,
                },
                state_version=state.get("state_version", 1),
            )

    return {
        "source_freshness": source_freshness,
        "data_conflicts": data_conflicts,
        "missing_fields": missing_fields,
        "confidence_report": confidence_report,
    }
