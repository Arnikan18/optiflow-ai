import logging
from typing import Dict, Any, Optional

logger = logging.getLogger("core-api.services.enterprise_monitor")

class EnterpriseEvents:
    NEW_TICKET = "NEW_TICKET"
    ENGINEER_RETURNED = "ENGINEER_RETURNED"
    PRIORITY_ESCALATED = "PRIORITY_ESCALATED"
    SPECIALIST_UNAVAILABLE = "SPECIALIST_UNAVAILABLE"
    SPECIALIST_RETURNED = "SPECIALIST_RETURNED"
    COMMENT_ADDED = "COMMENT_ADDED"
    METRIC_UPDATED = "METRIC_UPDATED"
    LOG_EMITTED = "LOG_EMITTED"

class EnterpriseMonitor:
    """Decision node that determines whether an operational change triggers a replanning solver run."""

    @staticmethod
    def should_replan(
        event: Optional[Dict[str, Any]],
        baseline_snapshot: Optional[Dict[str, Any]],
        current_state: Dict[str, Any]
    ) -> bool:
        """Lightweight replanning check. Evaluates event metadata first, falling back to state diffing."""
        # 1. No baseline means we must execute the initial planning run
        if not baseline_snapshot:
            logger.info("EnterpriseMonitor: No baseline snapshot found. Replan required.")
            return True

        # 2. Evaluate incoming event type if available
        if event:
            event_type = event.get("event_type") or event.get("type")
            if event_type:
                event_type_upper = str(event_type).upper()
                logger.info(f"EnterpriseMonitor: Evaluating event type {event_type_upper}")

                # Significant changes -> Replan
                if event_type_upper == EnterpriseEvents.NEW_TICKET:
                    priority = str(event.get("priority") or "LOW").upper()
                    # Replan only for High/Critical tickets
                    is_critical = priority in ("CRITICAL", "HIGH", "URGENT")
                    logger.info(f"EnterpriseMonitor: NEW_TICKET priority is {priority}. Replan: {is_critical}")
                    return is_critical

                if event_type_upper in (
                    EnterpriseEvents.ENGINEER_RETURNED,
                    EnterpriseEvents.PRIORITY_ESCALATED,
                    EnterpriseEvents.SPECIALIST_UNAVAILABLE,
                    EnterpriseEvents.SPECIALIST_RETURNED
                ):
                    logger.info(f"EnterpriseMonitor: Significant operational event {event_type_upper}. Replan: True")
                    return True

                # Insignificant changes -> Skip Replan
                if event_type_upper in (
                    EnterpriseEvents.COMMENT_ADDED,
                    EnterpriseEvents.METRIC_UPDATED,
                    EnterpriseEvents.LOG_EMITTED
                ):
                    logger.info(f"EnterpriseMonitor: Insignificant event {event_type_upper}. Replan: False")
                    return False

                # Default for other operational event types -> Replan
                logger.info(f"EnterpriseMonitor: Operational event {event_type_upper}. Replan: True")
                return True

        # 3. Fallback to lightweight snapshot diff if event metadata is absent
        logger.info("EnterpriseMonitor: Event metadata missing. Falling back to baseline diffing.")
        
        # Incident checks: counts, status, priorities
        prev_incidents = baseline_snapshot.get("incidents", [])
        curr_incidents = current_state.get("incidents", [])

        prev_map = {inc.get("incident_id"): inc for inc in prev_incidents if inc.get("incident_id")}
        curr_map = {inc.get("incident_id"): inc for inc in curr_incidents if inc.get("incident_id")}

        if set(prev_map.keys()) != set(curr_map.keys()):
            logger.info("EnterpriseMonitor: Incident count/ID mismatch. Replan: True")
            return True

        for inc_id, curr_inc in curr_map.items():
            prev_inc = prev_map.get(inc_id)
            if not prev_inc:
                return True
            if prev_inc.get("priority") != curr_inc.get("priority"):
                logger.info(f"EnterpriseMonitor: Incident {inc_id} priority changed. Replan: True")
                return True
            if prev_inc.get("status") != curr_inc.get("status"):
                logger.info(f"EnterpriseMonitor: Incident {inc_id} status changed. Replan: True")
                return True

        # Specialist checks: active status
        prev_specs = baseline_snapshot.get("specialists", [])
        curr_specs = current_state.get("specialists", [])
        prev_spec_map = {s.get("specialist_id"): s for s in prev_specs if s.get("specialist_id")}
        curr_spec_map = {s.get("specialist_id"): s for s in curr_specs if s.get("specialist_id")}

        if set(prev_spec_map.keys()) != set(curr_spec_map.keys()):
            logger.info("EnterpriseMonitor: Specialist list mismatch. Replan: True")
            return True

        for spec_id, curr_spec in curr_spec_map.items():
            prev_spec = prev_spec_map.get(spec_id)
            if not prev_spec:
                return True
            if prev_spec.get("active") != curr_spec.get("active"):
                logger.info(f"EnterpriseMonitor: Specialist {spec_id} active status changed. Replan: True")
                return True

        logger.info("EnterpriseMonitor: No significant changes observed. Replan: False")
        return False
