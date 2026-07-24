"""Evidence Planner module.

Translates the StructuredGoal objectives into distinct EvidenceRequirement configurations.
Queries the EvidenceRegistry as the single source of truth for service ownership, TTL,
and default importance configurations.
"""

from optiflow_shared.tool_contracts import StructuredGoal, EvidenceRequirement
from optiflow_shared.enums import EvidenceImportance, EvidenceType
from app.evidence.registry import EvidenceRegistry

def build_evidence_requirements(structured_goal: StructuredGoal) -> list[EvidenceRequirement]:
    """Translates interpreted goal objectives to specific EvidenceRequirements.
    
    Ensures that requirements are deduplicated and that default constraints (freshness TTL
    and importance levels) are resolved via the EvidenceRegistry.
    
    Args:
        structured_goal: The validated goal structured by the interpreter.
        
    Returns:
        List of compiled EvidenceRequirement objects.
    """
    requirements = {}
    registry = EvidenceRegistry()
    
    needs_customer_id = False
    
    for obj in structured_goal.objectives:
        evidence_types = registry.get_required_evidence(obj)
        for et in evidence_types:
            if et in (EvidenceType.CUSTOMER_ARR, EvidenceType.RENEWAL_DATE):
                needs_customer_id = True
                
            if et not in requirements:
                ttl = registry.get_ttl(et)
                importance = registry.get_default_importance(et)
                    
                requirements[et] = EvidenceRequirement(
                    evidence_type=et,
                    importance=importance,
                    entity_scope="GLOBAL",
                    reason=f"Required to evaluate objective {obj}",
                    freshness_seconds=ttl
                )
                
    # Add customer identity check if crm records (ARR or renewals) are required
    if needs_customer_id and EvidenceType.CUSTOMER_IDENTITY not in requirements:
        requirements[EvidenceType.CUSTOMER_IDENTITY] = EvidenceRequirement(
            evidence_type=EvidenceType.CUSTOMER_IDENTITY,
            importance=EvidenceImportance.REQUIRED,
            entity_scope="GLOBAL",
            reason="Required to resolve customer references across tool databases",
            freshness_seconds=registry.get_ttl(EvidenceType.CUSTOMER_IDENTITY)
        )
        
    return list(requirements.values())
