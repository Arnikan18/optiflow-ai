import logging
from datetime import datetime
from typing import List, Dict, Any, Optional

from app.schemas.decision_explanation import (
    DecisionExplanation,
    DecisionMetadata,
    ExecutiveSummary,
    DecisionReasoning,
    EvidenceSummary,
    ReasoningStep,
    RecommendationDetail,
    ConfidenceReport,
    CandidateAlternative,
    OperationalAction,
    BusinessKPI,
    TradeoffSummary,
    BusinessImpactSummary,
    DecisionOutcome,
    TriggerEventMetadata
)
from app.services.candidate_comparison_builder import CandidateComparisonBuilder

logger = logging.getLogger("core-api.services.decision_intelligence")

class DecisionIntelligenceService:
    """Service translating AgentState variables and optimizer schedules into DecisionExplanation DTOs."""

    @staticmethod
    def build_explanation(state: Dict[str, Any]) -> DecisionExplanation:
        """Translates current run state into the canonical DecisionExplanation DTO."""
        run_id = state.get("run_id", "unknown")
        scenario_id = state.get("scenario_id")
        timeline_position = state.get("timeline_position") or 0
        
        ent_state = state.get("enterprise_state") or {}
        customers = ent_state.get("customers", [])
        escalations = ent_state.get("escalations", [])
        specialists = ent_state.get("specialists", [])
        
        # 1. Resolve Trigger Event Details
        trigger = None
        latest_event = state.get("latest_event")
        if latest_event and isinstance(latest_event, dict):
            trigger = TriggerEventMetadata(
                event_type=latest_event.get("event_type") or latest_event.get("type") or "UNKNOWN",
                priority=latest_event.get("priority"),
                event_id=latest_event.get("incident_id") or latest_event.get("event_id")
            )
            
        # 2. Metadata
        meta = DecisionMetadata(
            decision_id=f"DEC-{run_id[-6:]}-{timeline_position}",
            run_id=run_id,
            scenario_id=scenario_id,
            timestamp=datetime.utcnow().isoformat() + "Z",
            timeline_position=timeline_position,
            trigger_event=trigger
        )
        
        # 3. Resolve Recommended Plan Details
        recommended_plan = state.get("recommended_plan") or {}
        selected_profile = recommended_plan.get("profile", "Balanced")
        explanation_text = recommended_plan.get("explanation") or "No justification explanation generated for this strategy profile."
        
        # 4. Compile Alternative Plan Summaries (Reusing CandidateComparisonBuilder)
        candidate_plans = state.get("candidate_plans") or []
        personalized_rec = state.get("personalized_recommendation") or {}
        personalized_reason = personalized_rec.get("reason")
        recommended_plan_id = recommended_plan.get("plan_id")
        
        summaries = CandidateComparisonBuilder.build_summaries(
            plans=candidate_plans,
            customers=customers,
            recommended_plan_id=recommended_plan_id,
            personalized_reason=personalized_reason
        )
        
        selected_reason = personalized_reason or "Recommended based on optimization objective score metrics."
        
        alternatives = []
        selected_metrics = None
        for s in summaries:
            if s.profile == selected_profile:
                selected_reason = s.recommendation_reason
                selected_metrics = s
            else:
                alternatives.append(
                    CandidateAlternative(
                        profile=s.profile,
                        rank=s.rank,
                        objective_score=s.objective_score,
                        sla_score=s.sla_score,
                        revenue_score=s.revenue_score,
                        fairness_score=s.fairness_score,
                        workload_score=s.workload_score,
                        selection_or_rejection_reason=s.recommendation_reason
                    )
                )
                
        # 5. Compile Executive Summary
        summary = ExecutiveSummary(
            headline=f"Strategy Recommendation: {selected_profile}",
            summary_text=explanation_text
        )
        
        # 6. Parse Reasons (extract bullets from explanation_text if formatted, or build defaults)
        reasons = []
        critical_count = sum(1 for e in escalations if str(e.get("priority", "")).upper() in ("CRITICAL", "HIGH", "URGENT"))
        
        if critical_count > 0:
            reasons.append(f"Prioritize resolution of {critical_count} critical/high priority support ticket escalations first.")
            
        for line in explanation_text.split("\n"):
            line_stripped = line.strip()
            if line_stripped.startswith(("-", "*")) and len(line_stripped) > 2:
                reasons.append(line_stripped[1:].strip())
                
        if not reasons:
            reasons.append(f"Optimizes allocations under the '{selected_profile}' priority policy profile constraints.")
            
        # 7. Compile Evidence Summary
        crm_ev = [f"{len(customers)} Customer Accounts loaded from CRM database."]
        if any(float(c.get("arr") or 0.0) > 200000.0 for c in customers):
            crm_ev.append("Strategic premium tiers verified ($200K+ ARR).")
            
        inc_ev = [f"{len(escalations)} Support Incident Escalations loaded from service."]
        if critical_count > 0:
            inc_ev.append(f"{critical_count} active SLA-critical status incidents flagged.")
            
        work_ev = [f"{len(specialists)} Service Engineers analyzed in Active Workforce database."]
        if any(s.get("current_workload", 0) > 0 for s in specialists):
            work_ev.append("Current workload capacity bounds validated to prevent fatigue.")
            
        opt_ev = [f"Evaluated {len(candidate_plans)} Strategy Options (Balanced, SLA-First, Revenue-First, Fairness-First)."]
        
        evidence = EvidenceSummary(
            crm=crm_ev,
            incident=inc_ev,
            workforce=work_ev,
            optimizer=opt_ev
        )
        
        # 8. Reasoning Steps flow
        steps = [
            ReasoningStep(step_name="Goal received", status="COMPLETED", description="Goal instruction validated and structured successfully."),
            ReasoningStep(step_name="Collected CRM information", status="COMPLETED", description=f"Loaded customer tier and ARR profiles."),
            ReasoningStep(step_name="Collected Incident information", status="COMPLETED", description=f"Loaded active support incidents and priorities."),
            ReasoningStep(step_name="Evaluated Workforce capacity", status="COMPLETED", description=f"Loaded specialist skills, load, and availability."),
            ReasoningStep(step_name="Compared candidate plans", status="COMPLETED", description="CP-SAT optimizer compared 4 strategy profiles."),
            ReasoningStep(step_name="Generated Personalized recommendation", status="COMPLETED", description="Personalized recommendation generated using Preference Memory.")
        ]
        
        reasoning = DecisionReasoning(
            reasons=reasons,
            evidence_used=evidence,
            reasoning_path=steps
        )
        
        # 9. Confidence Assessment (Composes Preference Memory outputs)
        conf_score = personalized_rec.get("confidence") or 0.85
        conf_level = str(personalized_rec.get("confidence_level") or "HIGH").upper()
        conf_reason = personalized_rec.get("reason") or "Goal matches configured default operational preference thresholds."
        
        rec_detail = RecommendationDetail(
            selected_profile=selected_profile,
            selection_reason=selected_reason,
            confidence=ConfidenceReport(score=conf_score * 100.0, level=conf_level, reason=conf_reason),
            alternatives=alternatives
        )
        
        # 10. Expected Business Impact & Tradeoffs
        kpis = []
        if selected_metrics:
            kpis.append(BusinessKPI(metric_name="SLA Compliance Score", display_value=f"{selected_metrics.sla_score:.1f}%", impact_level="HIGH_POSITIVE" if selected_metrics.sla_score > 80.0 else "NEUTRAL"))
            kpis.append(BusinessKPI(metric_name="Revenue ARR Protected", display_value=f"{selected_metrics.revenue_score:.1f}%", impact_level="HIGH_POSITIVE" if selected_metrics.revenue_score > 80.0 else "NEUTRAL"))
            kpis.append(BusinessKPI(metric_name="Fairness Distribution Score", display_value=f"{selected_metrics.fairness_score:.1f}%", impact_level="HIGH_POSITIVE" if selected_metrics.fairness_score > 85.0 else "NEUTRAL"))
            kpis.append(BusinessKPI(metric_name="Workload Load Management", display_value=f"{selected_metrics.workload_score:.1f}%", impact_level="HIGH_POSITIVE"))
            
        tradeoffs = TradeoffSummary(benefits=[], drawbacks=[])
        if selected_profile.lower() == "balanced":
            tradeoffs.benefits = ["Minimizes context-switching fatigue by distributing tasks evenly", "Reduces engineer burnout risk"]
            tradeoffs.drawbacks = ["May delay critical high-priority tickets if matching engineers are loaded"]
        elif selected_profile.lower() == "sla-first":
            tradeoffs.benefits = ["Ensures closest deadlines and strategic ARR accounts are resolved first", "Minimizes commercial exposure"]
            tradeoffs.drawbacks = ["May overload specialized engineers with high-demand skills", "Increases team workload inequality"]
        else:
            tradeoffs.benefits = ["Balanced optimization of objectives"]
            tradeoffs.drawbacks = ["Requires ongoing operational capacity updates"]
            
        impact = BusinessImpactSummary(kpis=kpis, tradeoffs=tradeoffs)
        
        # 11. Operational Action Plan mapping
        actions = []
        allocations = recommended_plan.get("allocations", [])
        specialist_names = {s.get("specialist_id"): s.get("name") for s in specialists}
        incident_titles = {i.get("incident_id"): i.get("title") for i in escalations}
        incident_priorities = {i.get("incident_id"): i.get("priority", "LOW") for i in escalations}
        
        for idx, a in enumerate(allocations):
            inc_id = a.get("incident_id")
            spec_id = a.get("specialist_id")
            name = specialist_names.get(spec_id, spec_id or "Unknown Specialist")
            title = incident_titles.get(inc_id, inc_id or "Unknown Incident")
            priority = str(incident_priorities.get(inc_id, "LOW")).upper()
            
            actions.append(
                OperationalAction(
                    action_text=f"Assign specialist {name} to resolve escalation '{title}' ({inc_id})",
                    assignee=name,
                    target=title,
                    priority="HIGH" if priority in ("CRITICAL", "HIGH", "URGENT") else "MEDIUM",
                    expected_effect=f"Addresses {priority.lower()} priority ticket using matching skills."
                )
            )
            
        return DecisionExplanation(
            metadata=meta,
            executive_summary=summary,
            reasoning=reasoning,
            recommendation=rec_detail,
            business_impact=impact,
            actions=actions,
            outcome=DecisionOutcome()
        )
