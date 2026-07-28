import asyncio
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import text

from app.config.settings import settings
from app.demo.schemas import (
    DemoCustomer,
    DemoHealthData,
    DemoIncident,
    DemoPortfolioData,
    DemoResetRequest,
    DemoSpecialist,
    DemoWorkload,
    FailureSimulationRequest,
    HealthComponent,
    PortfolioSummary,
    SimulationStateData,
    SourceStatusData,
    SpecialistResponseSimulationRequest,
)


ACTIVE_INCIDENT_STATUSES = {"OPEN", "IN_PROGRESS", "ESCALATED"}


@dataclass(frozen=True)
class SourceResult:
    name: str
    data: dict[str, Any] | None
    status: SourceStatusData


@dataclass
class SourceFailureRule:
    simulation_rule_id: int
    service: str
    enabled: bool
    failure_type: str
    status_code: int
    delay_seconds: int
    affected_endpoint: str | None
    scope: str | None
    apply_once: bool
    remaining_uses: int | None
    message: str | None
    created_at: str
    expires_at: str | None


_SOURCE_FAILURE_RULES: dict[str, SourceFailureRule] = {}
_NEXT_SOURCE_FAILURE_RULE_ID = 1


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def utc_timestamp() -> str:
    return utc_now().isoformat().replace("+00:00", "Z")


def parse_datetime(value: str | None) -> datetime | None:
    if value is None:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def parse_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def service_urls() -> dict[str, str]:
    return {
        "crm": settings.crm_service_url,
        "incident": settings.incident_service_url,
        "workforce": settings.workforce_service_url,
        "communication": settings.communication_service_url,
    }


def source_failure_state() -> dict[str, Any]:
    remove_expired_source_rules()
    return {
        service: {
            "simulation_rule_id": rule.simulation_rule_id,
            "enabled": rule.enabled,
            "failure_type": rule.failure_type,
            "status_code": rule.status_code,
            "delay_seconds": rule.delay_seconds,
            "affected_endpoint": rule.affected_endpoint,
            "scope": rule.scope,
            "apply_once": rule.apply_once,
            "remaining_uses": rule.remaining_uses,
            "message": rule.message,
            "created_at": rule.created_at,
            "expires_at": rule.expires_at,
        }
        for service, rule in sorted(_SOURCE_FAILURE_RULES.items())
    }


def remove_expired_source_rules() -> None:
    now = utc_now()
    for service, rule in list(_SOURCE_FAILURE_RULES.items()):
        expires_at = parse_datetime(rule.expires_at)
        if expires_at is not None and now >= expires_at:
            rule.enabled = False
            _SOURCE_FAILURE_RULES.pop(service, None)


def _consume_source_rule(rule: SourceFailureRule) -> None:
    if rule.remaining_uses is not None:
        rule.remaining_uses = max(rule.remaining_uses - 1, 0)
    if rule.apply_once or rule.remaining_uses == 0:
        rule.enabled = False
        _SOURCE_FAILURE_RULES.pop(rule.service, None)


def _source_service_name(source_name: str) -> str:
    return source_name.split("_", 1)[0]


def _rule_matches_endpoint(rule: SourceFailureRule, endpoint_name: str | None) -> bool:
    if rule.affected_endpoint and endpoint_name:
        configured = rule.affected_endpoint.strip().lower()
        if configured not in (endpoint_name.lower(), "*", "all"):
            return False
    if rule.scope and endpoint_name:
        configured_scope = rule.scope.strip().lower()
        endpoint_scope = endpoint_name.split(":", 1)[0].lower()
        if configured_scope not in (endpoint_scope, "*", "all"):
            return False
    return True


async def apply_source_failure_rule(source_name: str, endpoint_name: str | None) -> SourceResult | None:
    remove_expired_source_rules()
    service = _source_service_name(source_name)
    rule = _SOURCE_FAILURE_RULES.get(service)
    if rule is None or not rule.enabled or not _rule_matches_endpoint(rule, endpoint_name):
        return None

    started = time.perf_counter()
    if rule.delay_seconds:
        await asyncio.sleep(rule.delay_seconds)

    if rule.failure_type == "DELAY":
        _consume_source_rule(rule)
        return None

    if rule.failure_type == "TIMEOUT":
        source_status = "TIMEOUT"
        error_code = f"{service.upper()}_TIMEOUT"
        error_message = rule.message or "Source request timed out by demo simulation"
    elif rule.failure_type == "INVALID_RESPONSE":
        source_status = "INVALID_RESPONSE"
        error_code = f"{service.upper()}_INVALID_RESPONSE"
        error_message = rule.message or "Source returned invalid response by demo simulation"
    else:
        source_status = "UNAVAILABLE"
        error_code = f"{service.upper()}_{rule.status_code}"
        error_message = rule.message or "Source unavailable by demo simulation"

    _consume_source_rule(rule)
    return SourceResult(
        source_name,
        None,
        SourceStatusData(
            source_name=source_name,
            status=source_status,
            freshness_timestamp=None,
            response_time_ms=round((time.perf_counter() - started) * 1000, 2),
            error_code=error_code,
            error_message=error_message,
        ),
    )


def _service_headers(request_id: str, *, admin: bool = False) -> dict[str, str]:
    headers = {
        "X-Tool-Token": settings.tool_shared_token,
        "X-Request-ID": request_id,
        "Content-Type": "application/json",
    }
    if admin:
        headers["X-Admin-Key"] = settings.admin_api_key
    return headers


async def fetch_wrapped_source(
    *,
    source_name: str,
    base_url: str,
    path: str,
    request_id: str,
    timeout_seconds: float,
) -> SourceResult:
    simulated = await apply_source_failure_rule(source_name, source_name.replace("_", ":"))
    if simulated is not None:
        return simulated

    started = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            response = await client.get(f"{base_url}{path}", headers=_service_headers(request_id))
        response_time_ms = round((time.perf_counter() - started) * 1000, 2)
        try:
            body = response.json()
        except ValueError:
            return SourceResult(
                source_name,
                None,
                SourceStatusData(
                    source_name=source_name,
                    status="INVALID_RESPONSE",
                    freshness_timestamp=None,
                    response_time_ms=response_time_ms,
                    error_code=f"{source_name.upper()}_INVALID_RESPONSE",
                    error_message="Source returned non-JSON response",
                ),
            )

        if not isinstance(body, dict) or body.get("success") is not True or not isinstance(body.get("data"), dict):
            error_code = body.get("errorCode") if isinstance(body, dict) else None
            if response.status_code in (401, 403):
                source_status = "AUTH_FAILED"
            elif response.status_code == 504:
                source_status = "TIMEOUT"
            elif response.status_code >= 400:
                source_status = "UNAVAILABLE"
            else:
                source_status = "INVALID_RESPONSE"
            return SourceResult(
                source_name,
                None,
                SourceStatusData(
                    source_name=source_name,
                    status=source_status,
                    freshness_timestamp=body.get("timestamp") if isinstance(body, dict) else None,
                    response_time_ms=response_time_ms,
                    error_code=error_code or f"{source_name.upper()}_{response.status_code}",
                    error_message="Source did not return a valid success envelope",
                ),
            )

        return SourceResult(
            source_name,
            body["data"],
            SourceStatusData(
                source_name=source_name,
                status="AVAILABLE",
                freshness_timestamp=body.get("timestamp"),
                response_time_ms=response_time_ms,
            ),
        )
    except httpx.TimeoutException:
        return SourceResult(
            source_name,
            None,
            SourceStatusData(
                source_name=source_name,
                status="TIMEOUT",
                freshness_timestamp=None,
                response_time_ms=round((time.perf_counter() - started) * 1000, 2),
                error_code=f"{source_name.upper()}_TIMEOUT",
                error_message="Source request timed out",
            ),
        )
    except httpx.RequestError:
        return SourceResult(
            source_name,
            None,
            SourceStatusData(
                source_name=source_name,
                status="UNAVAILABLE",
                freshness_timestamp=None,
                response_time_ms=round((time.perf_counter() - started) * 1000, 2),
                error_code=f"{source_name.upper()}_UNAVAILABLE",
                error_message="Source is unavailable",
            ),
        )


def is_active_incident(incident: dict[str, Any]) -> bool:
    return str(incident.get("status", "")).upper() in ACTIVE_INCIDENT_STATUSES


def is_near_sla_breach(incident: dict[str, Any], now: datetime) -> bool | None:
    deadline = parse_datetime(incident.get("sla_deadline"))
    if deadline is None or not is_active_incident(incident):
        return None
    return deadline <= now + timedelta(hours=24)


def customer_priority(customer: dict[str, Any]) -> str | None:
    tier = str(customer.get("tier") or "").upper()
    arr = parse_float(customer.get("arr"))
    if tier == "ENTERPRISE" or (arr is not None and arr >= 500000):
        return "HIGH"
    if tier == "PREMIUM" or (arr is not None and arr >= 250000):
        return "MEDIUM"
    if tier:
        return "LOW"
    return None


def customer_renewal_risk(customer: dict[str, Any], incident_count: int, now: datetime) -> bool | None:
    renewal_date = customer.get("renewal_date")
    deadline = parse_datetime(f"{renewal_date}T00:00:00Z") if renewal_date else None
    if deadline is None:
        return True if incident_count > 0 else None
    return incident_count > 0 or deadline <= now + timedelta(days=90)


def assignment_status_by_incident(assignments: list[dict[str, Any]]) -> dict[str, str]:
    ordered = sorted(assignments, key=lambda item: str(item.get("created_at") or ""))
    status_by_incident: dict[str, str] = {}
    for assignment in ordered:
        incident_id = assignment.get("incident_id")
        if incident_id:
            status_by_incident[str(incident_id)] = str(assignment.get("status") or "")
    return status_by_incident


def build_portfolio(
    *,
    customers_data: dict[str, Any] | None,
    incidents_data: dict[str, Any] | None,
    specialists_data: dict[str, Any] | None,
    workloads_data: dict[str, Any] | None,
    assignments_data: dict[str, Any] | None,
    sources: list[SourceStatusData],
) -> DemoPortfolioData:
    now = utc_now()
    generated_at = now.isoformat().replace("+00:00", "Z")
    customers_raw = customers_data.get("customers", []) if customers_data else []
    incidents_raw = incidents_data.get("incidents", []) if incidents_data else []
    specialists_raw = specialists_data.get("specialists", []) if specialists_data else []
    workloads_raw = workloads_data.get("workloads", []) if workloads_data else []
    assignments_raw = assignments_data.get("assignment_requests", []) if assignments_data else []

    active_incident_counts: dict[str, int] = {}
    for incident in incidents_raw:
        if is_active_incident(incident):
            customer_id = str(incident.get("customer_id") or "")
            active_incident_counts[customer_id] = active_incident_counts.get(customer_id, 0) + 1

    customers = [
        DemoCustomer(
            customer_id=str(customer.get("customer_id") or ""),
            customer_name=str(customer.get("name") or customer.get("customer_name") or ""),
            segment=customer.get("tier") or customer.get("segment"),
            arr=parse_float(customer.get("arr")),
            business_value=parse_float(customer.get("arr") or customer.get("business_value")),
            renewal_date=customer.get("renewal_date"),
            renewal_risk=customer_renewal_risk(customer, active_incident_counts.get(str(customer.get("customer_id")), 0), now),
            strategic_priority=customer_priority(customer),
            current_incident_count=active_incident_counts.get(str(customer.get("customer_id")), 0),
        )
        for customer in customers_raw
    ]

    assignment_statuses = assignment_status_by_incident(assignments_raw)
    incidents = []
    for incident in incidents_raw:
        created_at = parse_datetime(incident.get("created_at"))
        age_hours = round((now - created_at).total_seconds() / 3600, 2) if created_at else None
        incidents.append(
            DemoIncident(
                incident_id=str(incident.get("incident_id") or ""),
                customer_id=str(incident.get("customer_id") or ""),
                title=incident.get("title"),
                summary=incident.get("description") or incident.get("summary"),
                severity=incident.get("severity") or incident.get("priority"),
                status=incident.get("status"),
                sla_deadline=incident.get("sla_deadline"),
                sla_risk=is_near_sla_breach(incident, now),
                required_skills=[],
                current_specialist_id=incident.get("assigned_specialist_id"),
                assignment_status=assignment_statuses.get(str(incident.get("incident_id") or "")),
                age_hours=age_hours,
                opened_at=incident.get("created_at"),
            )
        )

    workloads_by_specialist = {item.get("specialist_id"): item for item in workloads_raw}
    specialists = []
    for specialist in specialists_raw:
        specialist_id = specialist.get("specialist_id")
        workload = workloads_by_specialist.get(specialist_id, {})
        capacity = specialist.get("capacity")
        current_workload = specialist.get("current_workload")
        reserved_workload = None
        if "tentative_reservation_count" in workload:
            reserved_workload = int(workload.get("tentative_reservation_count") or 0)
        elif specialist.get("effective_workload") is not None and current_workload is not None:
            reserved_workload = max(int(specialist.get("effective_workload") or 0) - int(current_workload), 0)
        specialists.append(
            DemoSpecialist(
                specialist_id=str(specialist_id or ""),
                specialist_name=str(specialist.get("name") or ""),
                skills=list(specialist.get("skills") or []),
                availability=specialist.get("availability"),
                capacity=capacity,
                current_workload=current_workload,
                reserved_workload=reserved_workload,
                utilisation_percentage=workload.get("utilisation_percentage"),
                active_assignments=current_workload,
            )
        )

    workloads = [
        DemoWorkload(
            specialist_id=str(workload.get("specialist_id") or ""),
            assigned_count=workload.get("assigned_count"),
            tentative_reservation_count=workload.get("tentative_reservation_count"),
            confirmed_reservation_count=workload.get("confirmed_reservation_count"),
            available_capacity=workload.get("available_capacity"),
            utilisation_percentage=workload.get("utilisation_percentage"),
        )
        for workload in workloads_raw
    ]

    customer_arr_by_id = {customer.customer_id: customer.arr for customer in customers}
    at_risk_customer_ids = {customer.customer_id for customer in customers if customer.renewal_risk is True}
    for incident in incidents:
        if incident.sla_risk is True:
            at_risk_customer_ids.add(incident.customer_id)

    total_arr = sum(value for value in customer_arr_by_id.values() if value is not None) if customers_data else None
    arr_at_risk = (
        sum(customer_arr_by_id.get(customer_id) or 0 for customer_id in at_risk_customer_ids)
        if customers_data
        else None
    )
    workload_values = [
        item.utilisation_percentage
        for item in workloads
        if item.utilisation_percentage is not None
    ]

    summary = PortfolioSummary(
        total_customers=len(customers) if customers_data is not None else None,
        total_active_incidents=sum(1 for incident in incidents_raw if is_active_incident(incident)) if incidents_data else None,
        total_at_risk_customers=len(at_risk_customer_ids) if customers_data else None,
        total_arr_represented=round(total_arr, 2) if total_arr is not None else None,
        total_arr_at_risk=round(arr_at_risk, 2) if arr_at_risk is not None else None,
        total_specialists=len(specialists) if specialists_data else None,
        available_specialists=sum(1 for specialist in specialists_raw if specialist.get("operationally_available")) if specialists_data else None,
        average_workload=round(sum(workload_values) / len(workload_values), 2) if workload_values else None,
        incidents_near_sla_breach=sum(1 for incident in incidents if incident.sla_risk is True) if incidents_data else None,
        unassigned_incidents=sum(1 for incident in incidents_raw if is_active_incident(incident) and not incident.get("assigned_specialist_id")) if incidents_data else None,
        generated_at=generated_at,
        partial=any(source.status != "AVAILABLE" for source in sources),
    )

    return DemoPortfolioData(
        generated_at=generated_at,
        degraded=summary.partial,
        customers=customers,
        incidents=incidents,
        specialists=specialists,
        workloads=workloads,
        portfolio_summary=summary,
        sources=sources,
    )


async def get_demo_portfolio(request_id: str) -> DemoPortfolioData:
    timeout_seconds = settings.demo_portfolio_timeout_seconds
    urls = service_urls()
    tasks = [
        fetch_wrapped_source(
            source_name="crm",
            base_url=urls["crm"],
            path="/crm/api/v1/customers?page_size=100",
            request_id=request_id,
            timeout_seconds=timeout_seconds,
        ),
        fetch_wrapped_source(
            source_name="incident",
            base_url=urls["incident"],
            path="/incident/api/v1/incidents?page_size=100",
            request_id=request_id,
            timeout_seconds=timeout_seconds,
        ),
        fetch_wrapped_source(
            source_name="workforce",
            base_url=urls["workforce"],
            path="/workforce/api/v1/specialists?page_size=100",
            request_id=request_id,
            timeout_seconds=timeout_seconds,
        ),
        fetch_wrapped_source(
            source_name="workforce_workloads",
            base_url=urls["workforce"],
            path="/workforce/api/v1/workloads?page_size=100",
            request_id=request_id,
            timeout_seconds=timeout_seconds,
        ),
        fetch_wrapped_source(
            source_name="communication",
            base_url=urls["communication"],
            path="/communication/api/v1/assignment-requests?page_size=100",
            request_id=request_id,
            timeout_seconds=timeout_seconds,
        ),
    ]
    crm, incident, workforce, workloads, communication = await asyncio.gather(*tasks)
    return build_portfolio(
        customers_data=crm.data,
        incidents_data=incident.data,
        specialists_data=workforce.data,
        workloads_data=workloads.data,
        assignments_data=communication.data,
        sources=[item.status for item in (crm, incident, workforce, workloads, communication)],
    )


async def _check_service_health(name: str, base_url: str, request_id: str) -> HealthComponent:
    checked_at = utc_timestamp()
    started = time.perf_counter()
    try:
        async with httpx.AsyncClient(timeout=settings.demo_health_timeout_seconds) as client:
            response = await client.get(f"{base_url}/readiness", headers={"X-Request-ID": request_id})
        latency_ms = round((time.perf_counter() - started) * 1000, 2)
        if response.status_code == 200:
            return HealthComponent(name=name, status="HEALTHY", latency_ms=latency_ms, checked_at=checked_at)
        return HealthComponent(name=name, status="UNHEALTHY", latency_ms=latency_ms, checked_at=checked_at, message="Readiness check failed")
    except httpx.TimeoutException:
        return HealthComponent(name=name, status="UNHEALTHY", latency_ms=round((time.perf_counter() - started) * 1000, 2), checked_at=checked_at, message="Readiness timed out")
    except httpx.RequestError:
        return HealthComponent(name=name, status="UNHEALTHY", latency_ms=round((time.perf_counter() - started) * 1000, 2), checked_at=checked_at, message="Service unavailable")


async def get_demo_health(db: AsyncSession, request_id: str) -> DemoHealthData:
    checked_at = utc_timestamp()
    components = [HealthComponent(name="core-api", status="HEALTHY", latency_ms=0, checked_at=checked_at)]
    started = time.perf_counter()
    try:
        await db.execute(text("SELECT 1"))
        components.append(
            HealthComponent(
                name="postgres",
                status="HEALTHY",
                latency_ms=round((time.perf_counter() - started) * 1000, 2),
                checked_at=checked_at,
            )
        )
    except Exception:
        components.append(
            HealthComponent(
                name="postgres",
                status="UNHEALTHY",
                latency_ms=round((time.perf_counter() - started) * 1000, 2),
                checked_at=checked_at,
                message="Database readiness check failed",
            )
        )

    service_components = await asyncio.gather(
        *[
            _check_service_health(name, base_url, request_id)
            for name, base_url in service_urls().items()
        ]
    )
    components.extend(service_components)
    if any(item.name in {"core-api", "postgres"} and item.status == "UNHEALTHY" for item in components):
        overall = "UNHEALTHY"
    elif any(item.status == "UNHEALTHY" for item in components):
        overall = "DEGRADED"
    else:
        overall = "HEALTHY"
    return DemoHealthData(overall_status=overall, checked_at=checked_at, components=components)


async def _admin_request(
    *,
    service: str,
    path: str,
    method: str,
    request_id: str,
    json_body: dict[str, Any] | None = None,
) -> dict[str, Any]:
    base_url = service_urls()[service]
    try:
        async with httpx.AsyncClient(timeout=settings.tool_timeout_seconds) as client:
            response = await client.request(
                method,
                f"{base_url}{path}",
                headers=_service_headers(request_id, admin=True),
                json=json_body,
            )
    except httpx.RequestError:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"{service} admin endpoint unavailable") from None

    try:
        body = response.json()
    except ValueError:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"{service} returned invalid admin response") from None

    if response.status_code >= 400 or body.get("success") is not True:
        raise HTTPException(status_code=response.status_code, detail=f"{service} admin request failed")
    return body.get("data") or {}


async def queue_specialist_response(payload: SpecialistResponseSimulationRequest, request_id: str) -> dict[str, Any]:
    return await _admin_request(
        service="communication",
        path="/admin/next-response",
        method="POST",
        request_id=request_id,
        json_body=payload.model_dump(exclude_none=True),
    )


async def configure_failure(payload: FailureSimulationRequest, request_id: str) -> dict[str, Any]:
    global _NEXT_SOURCE_FAILURE_RULE_ID
    if payload.service != "communication":
        if payload.enabled:
            created_at = utc_timestamp()
            expires_at = None
            if payload.expires_after_seconds is not None:
                expires_at = (utc_now() + timedelta(seconds=payload.expires_after_seconds)).isoformat().replace("+00:00", "Z")
            rule = SourceFailureRule(
                simulation_rule_id=_NEXT_SOURCE_FAILURE_RULE_ID,
                service=payload.service,
                enabled=True,
                failure_type=payload.failure_type,
                status_code=payload.status_code,
                delay_seconds=payload.delay_seconds,
                affected_endpoint=payload.affected_endpoint,
                scope=payload.scope,
                apply_once=payload.apply_once,
                remaining_uses=1 if payload.apply_once else None,
                message=payload.message,
                created_at=created_at,
                expires_at=expires_at,
            )
            _SOURCE_FAILURE_RULES[payload.service] = rule
            _NEXT_SOURCE_FAILURE_RULE_ID += 1
            return source_failure_state()[payload.service]

        _SOURCE_FAILURE_RULES.pop(payload.service, None)
        return {
            "service": payload.service,
            "enabled": False,
            "active_rules": [],
        }

    body = payload.model_dump(exclude={"service"}, exclude_none=True)
    return await _admin_request(
        service=payload.service,
        path="/admin/failure-mode",
        method="POST",
        request_id=request_id,
        json_body=body,
    )


async def reset_demo(payload: DemoResetRequest | None, request_id: str) -> dict[str, Any]:
    services = payload.services if payload and payload.services else ["crm", "incident", "workforce", "communication"]
    results = {}
    degraded = False
    for service in services:
        _SOURCE_FAILURE_RULES.pop(service, None)
    for service in services:
        try:
            results[service] = await _admin_request(
                service=service,
                path="/admin/reset",
                method="POST",
                request_id=request_id,
            )
        except HTTPException as exc:
            degraded = True
            results[service] = {"status": "FAILED", "status_code": exc.status_code}
    return {"degraded": degraded, "services": results, "reset_at": utc_timestamp()}


async def get_simulation_state(request_id: str) -> SimulationStateData:
    services: dict[str, Any] = source_failure_state()
    degraded = False
    communication_state = None

    try:
        communication_failure = await _admin_request(
            service="communication",
            path="/admin/failure-mode",
            method="GET",
            request_id=request_id,
        )
        services["communication"] = communication_failure
        communication_state = await _admin_request(
            service="communication",
            path="/admin/simulation-state",
            method="GET",
            request_id=request_id,
        )
    except HTTPException:
        degraded = True

    return SimulationStateData(
        communication=communication_state,
        services=services,
        degraded=degraded,
        generated_at=utc_timestamp(),
    )
