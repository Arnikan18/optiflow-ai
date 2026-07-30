from datetime import datetime, timezone
from typing import Any

import httpx
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import settings
from app.database.models import SimulationEventHistory, SimulationNotification
from app.simulation.schemas import (
    ChangeEstimatedEffortPayload,
    ChangeSLAPayload,
    ChangeWorkerCapacityPayload,
    EngineerAvailabilityPayload,
    EnterpriseEventType,
    EscalatePriorityPayload,
    EventProcessingStatus,
    EVENT_PAYLOAD_MODELS,
    JudgeEventRequest,
    NewTicketPayload,
    NotificationStatus,
    ResolveTicketPayload,
    SimulationError,
    SimulationEventResult,
    TimelineEvent,
    utc_now,
)
from app.simulation.service_client import EnterpriseServiceClient


PRIORITY_RANK = {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}


def _json_datetime(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _payload_as_json(payload: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in payload.items():
        if isinstance(value, datetime):
            result[key] = _json_datetime(value)
        elif isinstance(value, list):
            result[key] = [
                _json_datetime(item) if isinstance(item, datetime) else item
                for item in value
            ]
        else:
            result[key] = value
    return result


class EnterpriseEventEngine:
    def __init__(self, client_factory: type[EnterpriseServiceClient] = EnterpriseServiceClient) -> None:
        self.client_factory = client_factory

    async def load_initial_state(
        self,
        *,
        scenario_id: str,
        initial_state,
        request_id: str,
    ) -> dict[str, Any]:
        client = self.client_factory(request_id)
        return await client.load_initial_state(scenario_id, initial_state)

    async def process_timeline_event(
        self,
        session: AsyncSession,
        event: TimelineEvent,
        *,
        simulation_id: str | None,
        request_id: str,
        current_stage: str | None,
    ) -> SimulationEventResult:
        request = JudgeEventRequest(
            event_id=event.event_id,
            scenario_id=event.scenario_id,
            event_type=event.event_type,
            payload=event.payload,
            description=event.description,
            effective_time=event.scheduled_time,
            idempotency_key=event.event_id,
        )
        return await self.process_event(
            session,
            request,
            simulation_id=simulation_id,
            request_id=request_id,
            current_stage=current_stage,
            current_simulation_time=event.scheduled_time,
        )

    async def process_event(
        self,
        session: AsyncSession,
        request: JudgeEventRequest,
        *,
        simulation_id: str | None,
        request_id: str,
        current_stage: str | None,
        current_simulation_time: datetime | None,
    ) -> SimulationEventResult:
        event_id = request.resolved_event_id()
        existing = await self._find_existing(session, event_id, request.idempotency_key)
        if existing is not None:
            return self._result_from_history(existing)

        validated_payload = self._validate_payload(request.event_type, request.payload)
        occurred_at = request.effective_time or utc_now()
        history = SimulationEventHistory(
            event_id=event_id,
            simulation_id=simulation_id,
            scenario_id=request.scenario_id,
            event_type=request.event_type.value,
            processing_status=EventProcessingStatus.RECEIVED.value,
            enterprise_changed=False,
            payload=_payload_as_json(validated_payload.model_dump(exclude_none=True)),
            changed_entities=[],
            error_details=[],
            notification_status=NotificationStatus.NOT_REQUIRED.value,
            idempotency_key=request.idempotency_key,
            request_id=request_id,
            occurred_at=occurred_at,
        )
        session.add(history)
        await session.flush()

        client = self.client_factory(request_id)
        try:
            changed_entities = await self._dispatch(client, request.event_type, validated_payload)
            enterprise_changed = bool(changed_entities)
            partial = any(str(item.get("change", "")).endswith("_failed") for item in changed_entities)
            processing_status = EventProcessingStatus.PARTIALLY_APPLIED if partial else EventProcessingStatus.APPLIED
            errors: list[dict[str, Any]] = []
        except SimulationError as exc:
            changed_entities = []
            enterprise_changed = False
            processing_status = EventProcessingStatus.FAILED
            errors = [{"error_code": exc.error_code, "message": exc.message, "details": exc.details}]

        applied_at = utc_now() if processing_status != EventProcessingStatus.FAILED else None
        notification_id = None
        notification_status = NotificationStatus.NOT_REQUIRED
        if enterprise_changed:
            notification_id, notification_status = await self._publish_notification(
                session,
                event_id=event_id,
                event_type=request.event_type,
                simulation_id=simulation_id,
                scenario_id=request.scenario_id,
                changed_entities=changed_entities,
                request_id=request_id,
                current_stage=current_stage,
                current_simulation_time=current_simulation_time,
            )
            if notification_status == NotificationStatus.DELIVERED:
                processing_status = EventProcessingStatus.NOTIFIED

        history.processing_status = processing_status.value
        history.enterprise_changed = enterprise_changed
        history.changed_entities = changed_entities
        history.error_details = errors
        history.notification_id = notification_id
        history.notification_status = notification_status.value
        history.applied_at = applied_at
        history.updated_at = utc_now()
        session.add(history)
        await session.flush()

        return SimulationEventResult(
            accepted=processing_status != EventProcessingStatus.FAILED,
            event_id=event_id,
            event_type=request.event_type,
            processing_status=processing_status,
            enterprise_changed=enterprise_changed,
            applied_at=applied_at,
            notification_status=notification_status,
            notification_id=notification_id,
            changed_entities=changed_entities,
            errors=errors,
        )

    async def list_event_history(
        self,
        session: AsyncSession,
        *,
        page: int,
        page_size: int,
        simulation_id: str | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        conditions = []
        if simulation_id:
            conditions.append(SimulationEventHistory.simulation_id == simulation_id)
        total_result = await session.execute(select(func.count(SimulationEventHistory.event_id)).where(*conditions))
        total = int(total_result.scalar_one() or 0)
        result = await session.execute(
            select(SimulationEventHistory)
            .where(*conditions)
            .order_by(SimulationEventHistory.created_at.desc(), SimulationEventHistory.event_id.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return [self._history_to_dict(item) for item in result.scalars().all()], total

    async def list_notifications(
        self,
        session: AsyncSession,
        *,
        page: int,
        page_size: int,
        status: str | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        conditions = []
        if status:
            conditions.append(SimulationNotification.status == status.strip().upper())
        total_result = await session.execute(select(func.count(SimulationNotification.notification_id)).where(*conditions))
        total = int(total_result.scalar_one() or 0)
        result = await session.execute(
            select(SimulationNotification)
            .where(*conditions)
            .order_by(SimulationNotification.created_at.desc(), SimulationNotification.notification_id.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return [self._notification_to_dict(item) for item in result.scalars().all()], total

    async def acknowledge_notification(
        self,
        session: AsyncSession,
        notification_id: str,
    ) -> dict[str, Any]:
        result = await session.execute(
            select(SimulationNotification).where(SimulationNotification.notification_id == notification_id.strip())
        )
        notification = result.scalar_one_or_none()
        if notification is None:
            raise SimulationError(404, "SIMULATION_NOTIFICATION_NOT_FOUND", "Simulation notification not found")
        notification.status = NotificationStatus.ACKNOWLEDGED.value
        notification.acknowledged_at = utc_now()
        notification.updated_at = utc_now()
        session.add(notification)
        await session.flush()
        return self._notification_to_dict(notification)

    async def _find_existing(
        self,
        session: AsyncSession,
        event_id: str,
        idempotency_key: str | None,
    ) -> SimulationEventHistory | None:
        result = await session.execute(select(SimulationEventHistory).where(SimulationEventHistory.event_id == event_id))
        existing = result.scalar_one_or_none()
        if existing is not None:
            return existing
        if not idempotency_key:
            return None
        result = await session.execute(
            select(SimulationEventHistory).where(SimulationEventHistory.idempotency_key == idempotency_key)
        )
        return result.scalar_one_or_none()

    def _validate_payload(self, event_type: EnterpriseEventType, payload: dict[str, Any]):
        model_type = EVENT_PAYLOAD_MODELS[event_type]
        try:
            return model_type.model_validate(payload)
        except ValidationError as exc:
            raise SimulationError(
                422,
                "SIMULATION_EVENT_PAYLOAD_INVALID",
                "Simulation event payload validation failed",
                details=[
                    {
                        "field": ".".join(str(part) for part in error.get("loc", ())),
                        "message": str(error.get("msg", "Invalid value")),
                    }
                    for error in exc.errors()
                ],
            ) from exc

    async def _dispatch(
        self,
        client: EnterpriseServiceClient,
        event_type: EnterpriseEventType,
        payload,
    ) -> list[dict[str, Any]]:
        if event_type == EnterpriseEventType.NEW_TICKET:
            return await self._new_ticket(client, payload)
        if event_type == EnterpriseEventType.RESOLVE_TICKET:
            return await self._resolve_ticket(client, payload)
        if event_type == EnterpriseEventType.ESCALATE_PRIORITY:
            return await self._escalate_priority(client, payload)
        if event_type == EnterpriseEventType.CHANGE_SLA:
            return await self._change_sla(client, payload)
        if event_type == EnterpriseEventType.CHANGE_ESTIMATED_EFFORT:
            return await self._change_estimated_effort(client, payload)
        if event_type == EnterpriseEventType.CHANGE_WORKER_CAPACITY:
            return await self._change_worker_capacity(client, payload)
        if event_type == EnterpriseEventType.ENGINEER_ON_LEAVE:
            return await self._engineer_availability(client, payload, available=False)
        if event_type == EnterpriseEventType.ENGINEER_RETURNED:
            return await self._engineer_availability(client, payload, available=True)
        raise SimulationError(422, "SIMULATION_EVENT_TYPE_UNSUPPORTED", "Unsupported simulation event type")

    async def _new_ticket(self, client: EnterpriseServiceClient, payload: NewTicketPayload) -> list[dict[str, Any]]:
        await client.get_customer(payload.customer_id)
        body = payload.model_dump(exclude_none=True)
        created = await client.create_incident(_payload_as_json(body))
        return [{"entity_type": "incident", "entity_id": created["incident_id"], "change": "created"}]

    async def _resolve_ticket(self, client: EnterpriseServiceClient, payload: ResolveTicketPayload) -> list[dict[str, Any]]:
        incident = await client.get_incident(payload.incident_id)
        if str(incident.get("status", "")).upper() in {"RESOLVED", "CLOSED"}:
            return []

        resolved = await client.resolve_incident(
            payload.incident_id,
            _payload_as_json(payload.model_dump(exclude_none=True)),
        )
        changed = [{"entity_type": "incident", "entity_id": resolved["incident_id"], "change": "resolved"}]
        try:
            release = await client.release_incident_workload(payload.incident_id, payload.resolution_note)
            if int(release.get("released_reservations", 0)) > 0:
                changed.append(
                    {
                        "entity_type": "workforce",
                        "entity_id": payload.incident_id,
                        "change": "released_workload",
                        "details": release,
                    }
                )
        except SimulationError as exc:
            changed.append(
                {
                    "entity_type": "workforce",
                    "entity_id": payload.incident_id,
                    "change": "release_failed",
                    "error_code": exc.error_code,
                }
            )
        return changed

    async def _escalate_priority(self, client: EnterpriseServiceClient, payload: EscalatePriorityPayload) -> list[dict[str, Any]]:
        incident = await client.get_incident(payload.incident_id)
        current_priority = str(incident.get("priority", "")).upper()
        if PRIORITY_RANK.get(payload.new_priority, 0) <= PRIORITY_RANK.get(current_priority, 0):
            raise SimulationError(409, "SIMULATION_PRIORITY_NOT_ESCALATED", "New priority must be higher than current priority")
        updated = await client.update_incident_fields(payload.incident_id, {"priority": payload.new_priority})
        return [{"entity_type": "incident", "entity_id": updated["incident_id"], "change": "priority_escalated"}]

    async def _change_sla(self, client: EnterpriseServiceClient, payload: ChangeSLAPayload) -> list[dict[str, Any]]:
        await client.get_incident(payload.incident_id)
        updated = await client.update_incident_fields(
            payload.incident_id,
            {"sla_deadline": _json_datetime(payload.sla_deadline)},
        )
        return [{"entity_type": "incident", "entity_id": updated["incident_id"], "change": "sla_changed"}]

    async def _change_estimated_effort(
        self,
        client: EnterpriseServiceClient,
        payload: ChangeEstimatedEffortPayload,
    ) -> list[dict[str, Any]]:
        await client.get_incident(payload.incident_id)
        updated = await client.update_incident_fields(
            payload.incident_id,
            {"estimated_effort_minutes": payload.estimated_effort_minutes},
        )
        return [{"entity_type": "incident", "entity_id": updated["incident_id"], "change": "estimated_effort_changed"}]

    async def _change_worker_capacity(
        self,
        client: EnterpriseServiceClient,
        payload: ChangeWorkerCapacityPayload,
    ) -> list[dict[str, Any]]:
        await client.get_specialist(payload.specialist_id)
        updated = await client.set_specialist_capacity(
            payload.specialist_id,
            capacity=payload.capacity,
            current_workload=payload.current_workload,
            reason=payload.reason,
        )
        return [
            {
                "entity_type": "specialist",
                "entity_id": updated["specialist_id"],
                "change": "worker_capacity_changed",
            }
        ]

    async def _engineer_availability(
        self,
        client: EnterpriseServiceClient,
        payload: EngineerAvailabilityPayload,
        *,
        available: bool,
    ) -> list[dict[str, Any]]:
        specialist = await client.get_specialist(payload.specialist_id)
        if bool(specialist.get("availability")) is available:
            return []
        updated = await client.set_specialist_availability(payload.specialist_id, available, payload.reason)
        change = "engineer_returned" if available else "engineer_on_leave"
        return [{"entity_type": "specialist", "entity_id": updated["specialist_id"], "change": change}]

    async def _publish_notification(
        self,
        session: AsyncSession,
        *,
        event_id: str,
        event_type: EnterpriseEventType,
        simulation_id: str | None,
        scenario_id: str | None,
        changed_entities: list[dict[str, Any]],
        request_id: str,
        current_stage: str | None,
        current_simulation_time: datetime | None,
    ) -> tuple[str, NotificationStatus]:
        notification_id = f"SIM-NOT-{event_id}"[:100]
        payload = {
            "notification_id": notification_id,
            "simulation_id": simulation_id,
            "scenario_id": scenario_id,
            "event_id": event_id,
            "event_type": event_type.value,
            "enterprise_changed": True,
            "changed_entities": changed_entities,
            "occurred_at": _json_datetime(utc_now()),
            "current_simulation_time": _json_datetime(current_simulation_time),
            "current_stage": current_stage,
            "correlation_id": event_id,
            "request_id": request_id,
        }
        status = NotificationStatus.PENDING
        attempt_count = 0
        last_error = None
        delivered_at = None

        if settings.simulation_event_callback_url:
            status, attempt_count, last_error, delivered_at = await self._deliver_callback(payload, request_id)

        notification = SimulationNotification(
            notification_id=notification_id,
            simulation_id=simulation_id,
            scenario_id=scenario_id,
            event_id=event_id,
            event_type=event_type.value,
            status=status.value,
            payload=payload,
            attempt_count=attempt_count,
            last_error=last_error,
            request_id=request_id,
            delivered_at=delivered_at,
        )
        session.add(notification)
        await session.flush()
        return notification_id, status

    async def _deliver_callback(
        self,
        payload: dict[str, Any],
        request_id: str,
    ) -> tuple[NotificationStatus, int, str | None, datetime | None]:
        attempts = max(settings.simulation_max_event_retries, 0) + 1
        last_error = None
        for attempt in range(1, attempts + 1):
            try:
                async with httpx.AsyncClient(timeout=settings.simulation_event_timeout_seconds) as client:
                    response = await client.post(
                        settings.simulation_event_callback_url,
                        headers={"X-Request-ID": request_id, "Content-Type": "application/json"},
                        json=payload,
                    )
                if response.status_code < 400:
                    return NotificationStatus.DELIVERED, attempt, None, utc_now()
                last_error = f"callback returned HTTP {response.status_code}"
            except httpx.RequestError as exc:
                last_error = str(exc)
        return NotificationStatus.FAILED, attempts, last_error, None

    def _result_from_history(self, history: SimulationEventHistory) -> SimulationEventResult:
        return SimulationEventResult(
            accepted=history.processing_status != EventProcessingStatus.FAILED.value,
            event_id=history.event_id,
            event_type=EnterpriseEventType(history.event_type),
            processing_status=EventProcessingStatus(history.processing_status),
            enterprise_changed=history.enterprise_changed,
            applied_at=history.applied_at,
            notification_status=NotificationStatus(history.notification_status),
            notification_id=history.notification_id,
            changed_entities=history.changed_entities or [],
            errors=history.error_details or [],
        )

    def _history_to_dict(self, item: SimulationEventHistory) -> dict[str, Any]:
        return {
            "event_id": item.event_id,
            "simulation_id": item.simulation_id,
            "scenario_id": item.scenario_id,
            "event_type": item.event_type,
            "processing_status": item.processing_status,
            "enterprise_changed": item.enterprise_changed,
            "payload": item.payload,
            "changed_entities": item.changed_entities or [],
            "errors": item.error_details or [],
            "notification_id": item.notification_id,
            "notification_status": item.notification_status,
            "idempotency_key": item.idempotency_key,
            "request_id": item.request_id,
            "occurred_at": _json_datetime(item.occurred_at),
            "applied_at": _json_datetime(item.applied_at),
            "created_at": _json_datetime(item.created_at),
            "updated_at": _json_datetime(item.updated_at),
        }

    def _notification_to_dict(self, item: SimulationNotification) -> dict[str, Any]:
        return {
            "notification_id": item.notification_id,
            "simulation_id": item.simulation_id,
            "scenario_id": item.scenario_id,
            "event_id": item.event_id,
            "event_type": item.event_type,
            "status": item.status,
            "payload": item.payload,
            "attempt_count": item.attempt_count,
            "last_error": item.last_error,
            "request_id": item.request_id,
            "created_at": _json_datetime(item.created_at),
            "delivered_at": _json_datetime(item.delivered_at),
            "acknowledged_at": _json_datetime(item.acknowledged_at),
            "updated_at": _json_datetime(item.updated_at),
        }


_engine: EnterpriseEventEngine | None = None


def get_event_engine() -> EnterpriseEventEngine:
    global _engine
    if _engine is None:
        _engine = EnterpriseEventEngine()
    return _engine
