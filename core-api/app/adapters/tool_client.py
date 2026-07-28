import httpx
import logging
from typing import Any, Dict, Optional, List
from fastapi import HTTPException, status
from uuid import uuid4
from app.config.settings import settings

logger = logging.getLogger("core-api.tool-client")

class ToolClient:
    """Adapter client for communicating with Member 2 enterprise microservices.
    
    Handles endpoint URL construction, header injection (X-Tool-Token, X-Request-ID),
    and safely extracts the structured 'data' block from standard success envelopes.
    """
    
    def __init__(self, request_id: Optional[str] = None):
        self.request_id = request_id or str(uuid4())
        self.headers = {
            "X-Tool-Token": settings.tool_shared_token,
            "X-Request-ID": self.request_id,
            "Content-Type": "application/json"
        }
        self.timeout = settings.tool_timeout_seconds

    async def _request(
        self,
        method: str,
        base_url: str,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        json_body: Optional[Dict[str, Any]] = None,
        use_admin_key: bool = False
    ) -> Any:
        headers = self.headers.copy()
        if use_admin_key:
            headers["X-Admin-Key"] = settings.admin_api_key

        url = f"{base_url}{path}"
        
        async with httpx.AsyncClient(headers=headers, timeout=self.timeout) as client:
            try:
                response = await client.request(
                    method=method,
                    url=url,
                    params=params,
                    json=json_body
                )
                response_json = response.json()
            except Exception as e:
                logger.error(f"HTTP request failed to {method} {url}: {str(e)}")
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"Outage or network failure connecting to downstream service {url}: {str(e)}"
                )

            # Check if response fits Member 2 wrapper
            success = response_json.get("success", False)
            if not success or response.status_code >= 400:
                msg = response_json.get("message", "Unknown error in tool-service")
                err_code = response_json.get("errorCode", f"SERVICE_{response.status_code}")
                logger.warning(f"Downstream service returned error: {err_code} - {msg}")
                raise HTTPException(
                    status_code=response.status_code,
                    detail={
                        "message": msg,
                        "errorCode": err_code
                    }
                )
                
            return response_json.get("data")

    # CRM Endpoints
    async def get_customers(self, active: Optional[bool] = None, tier: Optional[str] = None, search: Optional[str] = None) -> Dict[str, Any]:
        params = {}
        if active is not None:
            params["active"] = str(active).lower()
        if tier:
            params["tier"] = tier
        if search:
            params["search"] = search
        return await self._request("GET", settings.crm_service_url, "/crm/api/v1/customers", params=params)

    async def get_customer(self, customer_id: str) -> Dict[str, Any]:
        return await self._request("GET", settings.crm_service_url, f"/crm/api/v1/customers/{customer_id}")

    # Incident Endpoints
    async def get_incidents(self, status: Optional[str] = None, customer_id: Optional[str] = None) -> Dict[str, Any]:
        params = {}
        if status:
            params["status"] = status
        if customer_id:
            params["customer_id"] = customer_id
        return await self._request("GET", settings.incident_service_url, "/incident/api/v1/incidents", params=params)

    async def get_incident(self, incident_id: str) -> Dict[str, Any]:
        return await self._request("GET", settings.incident_service_url, f"/incident/api/v1/incidents/{incident_id}")

    async def patch_incident_status(self, incident_id: str, incident_status: str) -> Dict[str, Any]:
        return await self._request(
            "PATCH",
            settings.incident_service_url,
            f"/incident/api/v1/incidents/{incident_id}/status",
            json_body={"status": incident_status}
        )

    async def assign_incident_specialist(self, incident_id: str, specialist_id: str) -> Dict[str, Any]:
        return await self._request(
            "POST",
            settings.incident_service_url,
            f"/incident/api/v1/incidents/{incident_id}/assign",
            json_body={"specialist_id": specialist_id}
        )

    # Workforce Endpoints
    async def get_specialists(self, skill: Optional[str] = None) -> Dict[str, Any]:
        params = {}
        if skill:
            params["skill"] = skill
        return await self._request("GET", settings.workforce_service_url, "/workforce/api/v1/specialists", params=params)

    async def get_available_specialists(self, skill: str, required_capacity: int = 1) -> Dict[str, Any]:
        params = {
            "skill": skill,
            "required_capacity": required_capacity
        }
        return await self._request("GET", settings.workforce_service_url, "/workforce/api/v1/specialists/available", params=params)

    async def get_specialist(self, specialist_id: str) -> Dict[str, Any]:
        return await self._request("GET", settings.workforce_service_url, f"/workforce/api/v1/specialists/{specialist_id}")

    async def create_reservation(self, reservation_id: str, specialist_id: str, incident_id: str, expires_in_seconds: int = 300) -> Dict[str, Any]:
        body = {
            "reservation_id": reservation_id,
            "specialist_id": specialist_id,
            "incident_id": incident_id,
            "expires_in_seconds": expires_in_seconds
        }
        return await self._request("POST", settings.workforce_service_url, "/workforce/api/v1/reservations", json_body=body)

    async def get_reservation(self, reservation_id: str) -> Dict[str, Any]:
        return await self._request("GET", settings.workforce_service_url, f"/workforce/api/v1/reservations/{reservation_id}")

    async def confirm_reservation(self, reservation_id: str) -> Dict[str, Any]:
        return await self._request("PATCH", settings.workforce_service_url, f"/workforce/api/v1/reservations/{reservation_id}/confirm")

    async def cancel_reservation(self, reservation_id: str) -> Dict[str, Any]:
        return await self._request("DELETE", settings.workforce_service_url, f"/workforce/api/v1/reservations/{reservation_id}")

    # Communication Endpoints
    async def get_assignment_requests(self) -> Dict[str, Any]:
        return await self._request("GET", settings.communication_service_url, "/communication/api/v1/assignment-requests")

    async def get_assignment_request(self, request_id: str) -> Dict[str, Any]:
        return await self._request("GET", settings.communication_service_url, f"/communication/api/v1/assignment-requests/{request_id}")

    async def create_assignment_request(self, request_id: str, incident_id: str, specialist_id: str, message: str, expires_in_seconds: int = 300) -> Dict[str, Any]:
        body = {
            "request_id": request_id,
            "incident_id": incident_id,
            "specialist_id": specialist_id,
            "message": message,
            "expires_in_seconds": expires_in_seconds
        }
        return await self._request("POST", settings.communication_service_url, "/communication/api/v1/assignment-requests", json_body=body)

    async def respond_to_assignment_request(self, request_id: str, response: str, response_note: Optional[str] = None) -> Dict[str, Any]:
        body = {
            "response": response,
            "response_note": response_note
        }
        return await self._request("POST", settings.communication_service_url, f"/communication/api/v1/assignment-requests/{request_id}/respond", json_body=body)

    async def create_notification(self, notification_id: str, recipient: str, channel: str, message: str, related_request_id: Optional[str] = None, idempotency_key: Optional[str] = None) -> Dict[str, Any]:
        body = {
            "notification_id": notification_id,
            "recipient": recipient,
            "channel": channel,
            "message": message
        }
        if related_request_id:
            body["related_request_id"] = related_request_id
        if idempotency_key:
            body["idempotency_key"] = idempotency_key
            
        return await self._request("POST", settings.communication_service_url, "/communication/api/v1/notifications", json_body=body)

    # Admin Control Operations
    async def reset_db(self, base_url: str) -> Dict[str, Any]:
        return await self._request("POST", base_url, "/admin/reset", use_admin_key=True)
