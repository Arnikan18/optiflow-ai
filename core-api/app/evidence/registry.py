"""Evidence Registry module.

This module houses the static mappings for required evidence categories
needed to evaluate objectives, and registers the authoritative tool/service ownerships,
default importance thresholds, and freshness TTL (time-to-live) settings.
"""

from optiflow_shared.enums import ObjectiveType, EvidenceType, ToolService, EvidenceImportance

OBJECTIVE_EVIDENCE_MAP = {
    ObjectiveType.SLA_PROTECTION: [
        EvidenceType.ACTIVE_ESCALATIONS,
        EvidenceType.SLA_DEADLINES,
        EvidenceType.SEVERITY,
        EvidenceType.WORKAROUND_STATUS,
        EvidenceType.REQUIRED_SKILLS,
        EvidenceType.SPECIALIST_AVAILABILITY,
        EvidenceType.SPECIALIST_CAPACITY
    ],
    ObjectiveType.COMMERCIAL_PROTECTION: [
        EvidenceType.CUSTOMER_ARR,
        EvidenceType.CUSTOMER_TIER,
        EvidenceType.COMMERCIAL_DEPENDENCIES,
        EvidenceType.ACTIVE_ESCALATIONS
    ],
    ObjectiveType.RENEWAL_PROTECTION: [
        EvidenceType.RENEWAL_DATE,
        EvidenceType.RELATIONSHIP_CONTEXT,
        EvidenceType.ACTIVE_ESCALATIONS
    ],
    ObjectiveType.CUSTOMER_FAIRNESS: [
        EvidenceType.WAITING_TIME,
        EvidenceType.POSTPONEMENT_HISTORY,
        EvidenceType.CUSTOMER_TIER
    ],
    ObjectiveType.WORKLOAD_PROTECTION: [
        EvidenceType.CURRENT_WORKLOAD,
        EvidenceType.AFTER_HOURS_MINUTES,
        EvidenceType.OVERNIGHT_INCIDENT_COUNT,
        EvidenceType.RECENT_INTERRUPTION_COUNT
    ]
}

EVIDENCE_TOOL_REGISTRY = {
    # CRM
    EvidenceType.CUSTOMER_IDENTITY: ToolService.CRM,
    EvidenceType.CUSTOMER_ARR: ToolService.CRM,
    EvidenceType.CUSTOMER_TIER: ToolService.CRM,
    EvidenceType.RENEWAL_DATE: ToolService.CRM,
    EvidenceType.COMMERCIAL_DEPENDENCIES: ToolService.CRM,
    EvidenceType.RELATIONSHIP_CONTEXT: ToolService.CRM,
    
    # Incident
    EvidenceType.ACTIVE_ESCALATIONS: ToolService.INCIDENT,
    EvidenceType.SLA_DEADLINES: ToolService.INCIDENT,
    EvidenceType.SEVERITY: ToolService.INCIDENT,
    EvidenceType.WORKAROUND_STATUS: ToolService.INCIDENT,
    EvidenceType.REQUIRED_SKILLS: ToolService.INCIDENT,
    EvidenceType.REQUIRED_ACCESS: ToolService.INCIDENT,
    EvidenceType.CURRENT_ASSIGNMENT: ToolService.INCIDENT,
    EvidenceType.POSTPONEMENT_HISTORY: ToolService.INCIDENT,
    EvidenceType.WAITING_TIME: ToolService.INCIDENT,
    
    # Workforce
    EvidenceType.SPECIALIST_SKILLS: ToolService.WORKFORCE,
    EvidenceType.SPECIALIST_ACCESS: ToolService.WORKFORCE,
    EvidenceType.SPECIALIST_AVAILABILITY: ToolService.WORKFORCE,
    EvidenceType.SPECIALIST_CAPACITY: ToolService.WORKFORCE,
    EvidenceType.CURRENT_WORKLOAD: ToolService.WORKFORCE,
    EvidenceType.AFTER_HOURS_MINUTES: ToolService.WORKFORCE,
    EvidenceType.OVERNIGHT_INCIDENT_COUNT: ToolService.WORKFORCE,
    EvidenceType.RECENT_INTERRUPTION_COUNT: ToolService.WORKFORCE,
    
    # Communication
    EvidenceType.ASSIGNMENT_RESPONSE: ToolService.COMMUNICATION,
    EvidenceType.NOTIFICATION_STATUS: ToolService.COMMUNICATION
}

EVIDENCE_TTL_SECONDS = {
    EvidenceType.CUSTOMER_IDENTITY: 86400,
    EvidenceType.CUSTOMER_ARR: 86400,
    EvidenceType.CUSTOMER_TIER: 86400,
    EvidenceType.RENEWAL_DATE: 86400,
    EvidenceType.COMMERCIAL_DEPENDENCIES: 86400,
    EvidenceType.RELATIONSHIP_CONTEXT: 86400,
    
    EvidenceType.ACTIVE_ESCALATIONS: 120,
    EvidenceType.SLA_DEADLINES: 120,
    EvidenceType.SEVERITY: 120,
    EvidenceType.WORKAROUND_STATUS: 120,
    EvidenceType.REQUIRED_SKILLS: 120,
    EvidenceType.REQUIRED_ACCESS: 120,
    EvidenceType.CURRENT_ASSIGNMENT: 120,
    EvidenceType.POSTPONEMENT_HISTORY: 120,
    EvidenceType.WAITING_TIME: 120,
    
    EvidenceType.SPECIALIST_SKILLS: 60,
    EvidenceType.SPECIALIST_ACCESS: 60,
    EvidenceType.SPECIALIST_AVAILABILITY: 60,
    EvidenceType.SPECIALIST_CAPACITY: 60,
    EvidenceType.CURRENT_WORKLOAD: 60,
    EvidenceType.AFTER_HOURS_MINUTES: 60,
    EvidenceType.OVERNIGHT_INCIDENT_COUNT: 60,
    EvidenceType.RECENT_INTERRUPTION_COUNT: 60,
    
    EvidenceType.ASSIGNMENT_RESPONSE: 30,
    EvidenceType.NOTIFICATION_STATUS: 30
}

class EvidenceRegistry:
    """Registry class serving as the single source of truth for evidence configurations.
    
    Responsible for mapping goals to required evidence items, resolving service ownership,
    retrieving freshness thresholds, and defining default validation importance.
    
    Extension Points:
        - To add new objectives or evidence requirements, extend the mapping dictionaries.
    """
    def __init__(self):
        self._objective_map = OBJECTIVE_EVIDENCE_MAP
        self._tool_registry = EVIDENCE_TOOL_REGISTRY
        self._ttl_map = EVIDENCE_TTL_SECONDS

    def get_required_evidence(self, objective: ObjectiveType) -> list[EvidenceType]:
        """Returns the list of required evidence types for a given objective."""
        return self._objective_map.get(objective, [])

    def get_authoritative_tool(self, evidence: EvidenceType) -> ToolService:
        """Returns the ToolService enum indicating which service owns the evidence."""
        try:
            return self._tool_registry[evidence]
        except KeyError:
            raise ValueError(f"Unregistered evidence category: {evidence}")
            
    def get_ttl(self, evidence: EvidenceType) -> int:
        """Returns the max freshness age (in seconds) allowed for the evidence type."""
        return self._ttl_map.get(evidence, 3600)
        
    def get_default_importance(self, evidence: EvidenceType) -> EvidenceImportance:
        """Returns the default classification of evidence requirement urgency."""
        if evidence in (EvidenceType.SLA_DEADLINES, EvidenceType.SPECIALIST_AVAILABILITY):
            return EvidenceImportance.DECISION_CRITICAL
        elif evidence in (EvidenceType.POSTPONEMENT_HISTORY, EvidenceType.COMMERCIAL_DEPENDENCIES):
            return EvidenceImportance.OPTIONAL
        return EvidenceImportance.REQUIRED

    def get_all_registered_evidence(self) -> list[EvidenceType]:
        """Lists all registered evidence categories."""
        return list(self._tool_registry.keys())
