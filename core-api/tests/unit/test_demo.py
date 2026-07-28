import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.demo.routes import router
from app.demo.schemas import (
    DemoPortfolioData,
    PortfolioSummary,
    SourceStatusData,
)
from app.demo.service import (
    _SOURCE_FAILURE_RULES,
    apply_source_failure_rule,
    build_portfolio,
    configure_failure,
    utc_timestamp,
)


app = FastAPI()
app.include_router(router)
client = TestClient(app)


def source(name: str, status: str = "AVAILABLE") -> SourceStatusData:
    return SourceStatusData(
        source_name=name,
        status=status,
        freshness_timestamp=utc_timestamp() if status == "AVAILABLE" else None,
        response_time_ms=10.0,
        error_code=None if status == "AVAILABLE" else f"{name.upper()}_503",
        error_message=None if status == "AVAILABLE" else "unavailable",
    )


def test_build_portfolio_success_summary():
    portfolio = build_portfolio(
        customers_data={
            "customers": [
                {
                    "customer_id": "CUS-ALPHA",
                    "name": "Alpha Bank",
                    "tier": "Enterprise",
                    "arr": "600000.00",
                    "renewal_date": "2026-09-22",
                }
            ]
        },
        incidents_data={
            "incidents": [
                {
                    "incident_id": "INC-1",
                    "customer_id": "CUS-ALPHA",
                    "title": "Payment down",
                    "description": "Payment API outage",
                    "priority": "CRITICAL",
                    "status": "OPEN",
                    "sla_deadline": "2026-07-28T01:00:00Z",
                    "assigned_specialist_id": None,
                    "created_at": "2026-07-27T01:00:00Z",
                }
            ]
        },
        specialists_data={
            "specialists": [
                {
                    "specialist_id": "SPEC-MAYA",
                    "name": "Maya Sen",
                    "skills": ["technical"],
                    "availability": True,
                    "capacity": 2,
                    "current_workload": 0,
                    "operationally_available": True,
                }
            ]
        },
        workloads_data={
            "workloads": [
                {
                    "specialist_id": "SPEC-MAYA",
                    "assigned_count": 0,
                    "tentative_reservation_count": 1,
                    "confirmed_reservation_count": 0,
                    "available_capacity": 1,
                    "utilisation_percentage": 50.0,
                }
            ]
        },
        assignments_data={"assignment_requests": [{"incident_id": "INC-1", "status": "PENDING"}]},
        sources=[source("crm"), source("incident"), source("workforce"), source("workforce_workloads"), source("communication")],
    )

    assert portfolio.degraded is False
    assert portfolio.customers[0].current_incident_count == 1
    assert portfolio.incidents[0].assignment_status == "PENDING"
    assert portfolio.specialists[0].reserved_workload == 1
    assert portfolio.portfolio_summary.total_customers == 1
    assert portfolio.portfolio_summary.unassigned_incidents == 1


def test_build_portfolio_partial_crm_unavailable():
    portfolio = build_portfolio(
        customers_data=None,
        incidents_data={"incidents": []},
        specialists_data={"specialists": []},
        workloads_data={"workloads": []},
        assignments_data={"assignment_requests": []},
        sources=[source("crm", "UNAVAILABLE"), source("incident"), source("workforce"), source("workforce_workloads"), source("communication")],
    )

    assert portfolio.degraded is True
    assert portfolio.customers == []
    assert portfolio.portfolio_summary.total_customers is None
    assert portfolio.sources[0].error_code == "CRM_503"


@pytest.mark.asyncio
async def test_core_source_failure_simulation_consumes_one_time_rule():
    _SOURCE_FAILURE_RULES.clear()

    class Payload:
        service = "crm"
        enabled = True
        failure_type = "HTTP_ERROR"
        status_code = 503
        delay_seconds = 0
        affected_endpoint = None
        scope = None
        apply_once = True
        expires_after_seconds = None
        message = "CRM unavailable"

    configured = await configure_failure(Payload(), "REQ-DEMO")
    assert configured["enabled"] is True

    first = await apply_source_failure_rule("crm", "crm:list")
    assert first is not None
    assert first.status.status == "UNAVAILABLE"

    second = await apply_source_failure_rule("crm", "crm:list")
    assert second is None


def test_demo_portfolio_route_uses_standard_wrapper(monkeypatch):
    async def fake_portfolio(request_id):
        generated_at = utc_timestamp()
        return DemoPortfolioData(
            generated_at=generated_at,
            degraded=False,
            customers=[],
            incidents=[],
            specialists=[],
            workloads=[],
            portfolio_summary=PortfolioSummary(
                total_customers=0,
                total_active_incidents=0,
                total_at_risk_customers=0,
                total_arr_represented=0,
                total_arr_at_risk=0,
                total_specialists=0,
                available_specialists=0,
                average_workload=0,
                incidents_near_sla_breach=0,
                unassigned_incidents=0,
                generated_at=generated_at,
                partial=False,
            ),
            sources=[],
        )

    monkeypatch.setattr("app.demo.routes.get_demo_portfolio", fake_portfolio)
    response = client.get("/api/v1/demo/portfolio", headers={"X-Request-ID": "REQ-DEMO-PORTFOLIO"})
    body = response.json()
    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "REQ-DEMO-PORTFOLIO"
    assert body["success"] is True
    assert body["data"]["degraded"] is False


def test_simulation_routes_require_demo_mode(monkeypatch):
    from app.config.settings import settings

    monkeypatch.setattr(settings, "demo_mode", False)
    response = client.get("/api/v1/demo/simulation/state")
    assert response.status_code == 403
