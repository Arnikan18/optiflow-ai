from typing import Any

import httpx

from app.config.settings import settings
from app.simulation.schemas import InitialState, SimulationError


class EnterpriseServiceClient:
    def __init__(self, request_id: str) -> None:
        self.request_id = request_id

    def _headers(self, *, admin: bool = False) -> dict[str, str]:
        headers = {
            "X-Tool-Token": settings.tool_shared_token,
            "X-Request-ID": self.request_id,
            "Content-Type": "application/json",
        }
        if admin:
            headers["X-Admin-Key"] = settings.admin_api_key
        return headers

    async def _request(
        self,
        method: str,
        base_url: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
        admin: bool = False,
    ) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(timeout=settings.tool_timeout_seconds) as client:
                response = await client.request(
                    method,
                    f"{base_url}{path}",
                    headers=self._headers(admin=admin),
                    json=json_body,
                )
        except httpx.RequestError as exc:
            raise SimulationError(
                502,
                "SIMULATION_DOWNSTREAM_UNAVAILABLE",
                "Enterprise service is unavailable",
                details=[{"service_url": base_url, "path": path}],
            ) from exc

        try:
            body = response.json()
        except ValueError as exc:
            raise SimulationError(
                502,
                "SIMULATION_DOWNSTREAM_INVALID_RESPONSE",
                "Enterprise service returned a non-JSON response",
                details=[{"service_url": base_url, "path": path, "status_code": response.status_code}],
            ) from exc

        if response.status_code >= 400 or not isinstance(body, dict) or body.get("success") is not True:
            details = {
                "service_url": base_url,
                "path": path,
                "status_code": response.status_code,
            }
            if isinstance(body, dict):
                details["downstream_error_code"] = body.get("errorCode")
                details["downstream_message"] = body.get("message")
            raise SimulationError(
                response.status_code if response.status_code >= 400 else 502,
                "SIMULATION_DOWNSTREAM_REJECTED",
                "Enterprise service rejected the simulation request",
                details=[details],
            )
        data = body.get("data")
        return data if isinstance(data, dict) else {"value": data}

    async def load_initial_state(self, scenario_id: str, initial_state: InitialState) -> dict[str, Any]:
        results: dict[str, Any] = {}
        results["crm"] = await self._request(
            "POST",
            settings.crm_service_url,
            "/admin/simulation/load-state",
            json_body={"scenario_id": scenario_id, "customers": initial_state.customers},
            admin=True,
        )
        results["workforce"] = await self._request(
            "POST",
            settings.workforce_service_url,
            "/admin/simulation/load-state",
            json_body={
                "scenario_id": scenario_id,
                "specialists": initial_state.specialists,
                "reservations": initial_state.reservations,
                "workloads": initial_state.workloads,
            },
            admin=True,
        )
        results["incident"] = await self._request(
            "POST",
            settings.incident_service_url,
            "/admin/simulation/load-state",
            json_body={"scenario_id": scenario_id, "incidents": initial_state.incidents},
            admin=True,
        )
        results["communication"] = await self._request(
            "POST",
            settings.communication_service_url,
            "/admin/simulation/load-state",
            json_body={
                "scenario_id": scenario_id,
                "assignment_requests": initial_state.assignments,
                "notifications": initial_state.notifications,
            },
            admin=True,
        )
        return results

    async def get_customer(self, customer_id: str) -> dict[str, Any]:
        return await self._request("GET", settings.crm_service_url, f"/crm/api/v1/customers/{customer_id}")

    async def get_incident(self, incident_id: str) -> dict[str, Any]:
        return await self._request("GET", settings.incident_service_url, f"/incident/api/v1/incidents/{incident_id}")

    async def create_incident(self, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._request("POST", settings.incident_service_url, "/incident/api/v1/incidents", json_body=payload)

    async def update_incident_fields(self, incident_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._request(
            "PATCH",
            settings.incident_service_url,
            f"/incident/api/v1/incidents/{incident_id}/simulation-fields",
            json_body=payload,
        )

    async def resolve_incident(self, incident_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._request(
            "POST",
            settings.incident_service_url,
            f"/incident/api/v1/incidents/{incident_id}/simulation-resolve",
            json_body=payload,
        )

    async def get_specialist(self, specialist_id: str) -> dict[str, Any]:
        return await self._request("GET", settings.workforce_service_url, f"/workforce/api/v1/specialists/{specialist_id}")

    async def set_specialist_availability(self, specialist_id: str, available: bool, reason: str | None) -> dict[str, Any]:
        return await self._request(
            "PATCH",
            settings.workforce_service_url,
            f"/workforce/api/v1/specialists/{specialist_id}/simulation-availability",
            json_body={"availability": available, "reason": reason},
        )

    async def set_specialist_capacity(
        self,
        specialist_id: str,
        *,
        capacity: int | None,
        current_workload: int | None,
        reason: str | None,
    ) -> dict[str, Any]:
        return await self._request(
            "PATCH",
            settings.workforce_service_url,
            f"/workforce/api/v1/specialists/{specialist_id}/simulation-capacity",
            json_body={
                key: value
                for key, value in {
                    "capacity": capacity,
                    "current_workload": current_workload,
                    "reason": reason,
                }.items()
                if value is not None
            },
        )

    async def release_incident_workload(self, incident_id: str, reason: str | None) -> dict[str, Any]:
        return await self._request(
            "POST",
            settings.workforce_service_url,
            f"/workforce/api/v1/incidents/{incident_id}/release-workload",
            json_body={"reason": reason},
        )
