from datetime import datetime

from fastapi import APIRouter, Depends, Header, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database.session import get_db
from app.middleware.authentication import verify_tool_token
from app.schemas.requests import (
    AdminConfiguredResponseRequest,
    AdminFailureModeRequest,
    AssignmentRequestCreateRequest,
    AssignmentRequestVerificationRequest,
    AssignmentResponseRequest,
    LegacyAssignmentCreateRequest,
    LegacyAssignmentResponseRequest,
    LegacyNotificationCreateRequest,
    NotificationCreateRequest,
)
from app.schemas.responses import (
    AssignmentRequestListData,
    AssignmentRequestResponse,
    AssignmentRequestVerificationResponse,
    ConfiguredResponseData,
    FailureModeData,
    FailureModeStateData,
    NotificationListData,
    NotificationResponse,
    ResetResponseData,
    SimulationStateData,
    success_response,
)
from app.services.assignment_service import (
    CommunicationError,
    configure_failure_mode,
    assignment_to_legacy_dict,
    configure_legacy_response,
    create_assignment_request,
    create_legacy_assignment_request,
    get_assignment_request,
    get_failure_mode,
    get_simulation_state,
    list_active_failure_modes,
    list_assignment_requests,
    reset_communication,
    respond_to_assignment_request,
    verify_assignment_request,
)
from app.services.failure_service import apply_failure_mode
from app.services.notification_service import (
    create_legacy_notification,
    create_notification,
    get_notification,
    list_notifications,
    notification_to_legacy_dict,
)


router = APIRouter(
    prefix="/communication/api/v1",
    tags=["communication"],
    dependencies=[Depends(verify_tool_token)],
)
admin_router = APIRouter(tags=["admin"])
legacy_router = APIRouter(
    tags=["legacy-communication"],
    dependencies=[Depends(verify_tool_token)],
)


def _assignment_data(request) -> dict:
    return AssignmentRequestResponse.model_validate(request).model_dump(mode="json")


def _notification_data(notification) -> dict:
    return NotificationResponse.model_validate(notification).model_dump(mode="json")


@router.post("/assignment-requests", status_code=201)
async def create_assignment_request_record(
    payload: AssignmentRequestCreateRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    await apply_failure_mode(db, "assignment:create")
    assignment_request, created = await create_assignment_request(db, payload)
    if not created:
        response.status_code = 200
        return success_response(_assignment_data(assignment_request), message="Assignment request already exists")
    return success_response(_assignment_data(assignment_request), message="Assignment request created successfully")


@router.get("/assignment-requests")
async def get_assignment_requests(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status: str | None = Query(default=None),
    incident_id: str | None = Query(default=None),
    specialist_id: str | None = Query(default=None),
    pending_only: bool = Query(default=False),
    expired: bool | None = Query(default=None),
    created_after: datetime | None = Query(default=None),
    created_before: datetime | None = Query(default=None),
    search: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    await apply_failure_mode(db, "assignment:list")
    result = await list_assignment_requests(
        db,
        page=page,
        page_size=page_size,
        status=status,
        incident_id=incident_id,
        specialist_id=specialist_id,
        pending_only=pending_only,
        expired=expired,
        created_after=created_after,
        created_before=created_before,
        search=search,
    )
    data = AssignmentRequestListData(
        assignment_requests=[AssignmentRequestResponse.model_validate(item) for item in result.assignment_requests],
        page=result.page,
        page_size=result.page_size,
        total_items=result.total_items,
        total_pages=result.total_pages,
    )
    return success_response(data.model_dump(mode="json"))


@router.get("/assignment-requests/{request_id}")
async def get_assignment_request_by_id(request_id: str, db: AsyncSession = Depends(get_db)):
    await apply_failure_mode(db, "assignment:get")
    assignment_request = await get_assignment_request(db, request_id)
    return success_response(_assignment_data(assignment_request))


@router.post("/assignment-requests/verify")
async def verify_assignment_request_record(
    payload: AssignmentRequestVerificationRequest,
    db: AsyncSession = Depends(get_db),
):
    await apply_failure_mode(db, "assignment:verify")
    data = await verify_assignment_request(db, payload)
    return success_response(AssignmentRequestVerificationResponse(**data).model_dump(mode="json"))


@router.post("/assignment-requests/{request_id}/respond")
async def respond_to_assignment_request_record(
    request_id: str,
    payload: AssignmentResponseRequest,
    db: AsyncSession = Depends(get_db),
):
    await apply_failure_mode(db, "assignment:respond")
    assignment_request = await respond_to_assignment_request(db, request_id, payload)
    return success_response(_assignment_data(assignment_request), message="Assignment response recorded successfully")


@router.post("/notifications", status_code=201)
async def create_notification_record(
    payload: NotificationCreateRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    await apply_failure_mode(db, "notification:create")
    result = await create_notification(db, payload)
    if not result.created:
        response.status_code = 200
        return success_response(_notification_data(result.notification), message="Notification already exists")
    if result.notification.status == "FAILED":
        return success_response(_notification_data(result.notification), message="Notification created; simulated delivery failed")
    return success_response(_notification_data(result.notification), message="Notification created and delivered")


@router.get("/notifications")
async def get_notifications(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status: str | None = Query(default=None),
    channel: str | None = Query(default=None),
    recipient: str | None = Query(default=None),
    related_request_id: str | None = Query(default=None),
    created_after: datetime | None = Query(default=None),
    created_before: datetime | None = Query(default=None),
    search: str | None = Query(default=None),
    db: AsyncSession = Depends(get_db),
):
    await apply_failure_mode(db, "notification:list")
    result = await list_notifications(
        db,
        page=page,
        page_size=page_size,
        status=status,
        channel=channel,
        recipient=recipient,
        related_request_id=related_request_id,
        created_after=created_after,
        created_before=created_before,
        search=search,
    )
    data = NotificationListData(
        notifications=[NotificationResponse.model_validate(item) for item in result.notifications],
        page=result.page,
        page_size=result.page_size,
        total_items=result.total_items,
        total_pages=result.total_pages,
    )
    return success_response(data.model_dump(mode="json"))


@router.get("/notifications/{notification_id}")
async def get_notification_by_id(notification_id: str, db: AsyncSession = Depends(get_db)):
    await apply_failure_mode(db, "notification:get")
    notification = await get_notification(db, notification_id)
    return success_response(_notification_data(notification))


def verify_admin_key(x_admin_key: str | None = Header(default=None, alias="X-Admin-Key")) -> None:
    settings = get_settings()
    if not settings.admin_api_key:
        raise CommunicationError(503, "COMMUNICATION_503", "Admin reset is not configured")
    if x_admin_key != settings.admin_api_key:
        raise CommunicationError(401, "COMMUNICATION_401", "Invalid admin credentials")


@admin_router.post("/admin/reset", dependencies=[Depends(verify_admin_key)])
async def reset_communication_database(db: AsyncSession = Depends(get_db)):
    counts = await reset_communication(db)
    data = ResetResponseData(**counts)
    return success_response(data.model_dump(mode="json"), message="Communication database reset successfully")


@admin_router.post("/admin/next-response", dependencies=[Depends(verify_admin_key)])
async def configure_next_response(payload: AdminConfiguredResponseRequest, db: AsyncSession = Depends(get_db)):
    delay_seconds = payload.response_delay_seconds
    if payload.delayMs is not None:
        delay_seconds = int(payload.delayMs / 1000)

    configured = await configure_legacy_response(
        db,
        specialist_id=payload.specialist_id,
        incident_id=payload.incident_id,
        status=payload.status,
        reason=payload.reason,
        delay_seconds=delay_seconds,
        apply_once=payload.apply_once,
        expires_after_seconds=payload.expires_after_seconds,
    )
    data = _configured_response_data(configured)
    return success_response(data, message="Queued response configured")


def _configured_response_data(configured) -> dict:
    return ConfiguredResponseData(
        simulation_rule_id=configured.configuration_id,
        specialist_id=configured.specialist_id,
        incident_id=configured.incident_id,
        status=configured.next_status,
        reason=configured.response_reason,
        response_delay_seconds=configured.delay_seconds,
        apply_once=bool(configured.apply_once),
        active=bool(configured.active),
        created_at=configured.created_at,
        expires_at=configured.expires_at,
        consumed_at=configured.consumed_at,
    ).model_dump(mode="json")


def _failure_mode_data(mode) -> dict:
    return FailureModeData(
        simulation_rule_id=mode.mode_id,
        enabled=bool(mode.enabled),
        failure_type=mode.failure_type,
        status_code=mode.status_code,
        delay_seconds=mode.delay_seconds,
        affected_endpoint=mode.affected_endpoint,
        scope=mode.scope,
        apply_once=bool(mode.apply_once),
        remaining_uses=mode.remaining_failures,
        message=mode.message,
        created_at=mode.created_at,
        expires_at=mode.expires_at,
    ).model_dump(mode="json")


@admin_router.get("/admin/failure-mode", dependencies=[Depends(verify_admin_key)])
async def read_failure_mode(db: AsyncSession = Depends(get_db)):
    active_rules = [_failure_mode_data(rule) for rule in await list_active_failure_modes(db)]
    enabled = any(rule["enabled"] for rule in active_rules)
    if not active_rules:
        mode = await get_failure_mode(db)
        return success_response(
            FailureModeStateData(enabled=bool(mode.enabled), active_rules=[]).model_dump(mode="json")
        )
    return success_response(FailureModeStateData(enabled=enabled, active_rules=active_rules).model_dump(mode="json"))


@admin_router.post("/admin/failure-mode", dependencies=[Depends(verify_admin_key)])
async def update_failure_mode(payload: AdminFailureModeRequest, db: AsyncSession = Depends(get_db)):
    mode = await configure_failure_mode(
        db,
        enabled=payload.enabled,
        failure_type=payload.failure_type,
        status_code=payload.status_code,
        delay_seconds=payload.delay_seconds,
        affected_endpoint=payload.affected_endpoint,
        scope=payload.scope,
        apply_once=payload.apply_once,
        expires_after_seconds=payload.expires_after_seconds,
        message=payload.message,
    )
    return success_response(_failure_mode_data(mode), message="Failure mode updated")


@admin_router.get("/admin/simulation-state", dependencies=[Depends(verify_admin_key)])
async def read_simulation_state(db: AsyncSession = Depends(get_db)):
    state = await get_simulation_state(db)
    data = SimulationStateData(
        queued_specialist_responses=[_configured_response_data(item) for item in state["queued_specialist_responses"]],
        active_failure_modes=[_failure_mode_data(item) for item in state["active_failure_modes"]],
        pending_assignment_requests=[
            AssignmentRequestResponse.model_validate(item) for item in state["pending_assignment_requests"]
        ],
        last_reset_at=state["last_reset_at"],
        demo_seed_status=state["demo_seed_status"],
    )
    return success_response(data.model_dump(mode="json"))


@legacy_router.get("/assignment-requests", deprecated=True)
async def get_legacy_assignment_requests(db: AsyncSession = Depends(get_db)):
    result = await list_assignment_requests(db, page=1, page_size=100)
    return [assignment_to_legacy_dict(item) for item in result.assignment_requests]


@legacy_router.post("/assignment-requests", deprecated=True)
async def create_legacy_assignment_request_record(
    payload: LegacyAssignmentCreateRequest,
    db: AsyncSession = Depends(get_db),
):
    assignment_request = await create_legacy_assignment_request(
        db,
        specialist_id=payload.specialistId,
        incident_id=payload.escalationId,
        message=payload.message,
        idempotency_key=payload.idempotencyKey,
        run_id=payload.runId,
        reservation_id=payload.reservationId,
    )
    return assignment_to_legacy_dict(assignment_request)


@legacy_router.get("/assignment-requests/{request_id}", deprecated=True)
async def get_legacy_assignment_request(request_id: str, db: AsyncSession = Depends(get_db)):
    assignment_request = await get_assignment_request(db, request_id)
    return assignment_to_legacy_dict(assignment_request)


@legacy_router.post("/assignment-requests/{request_id}/respond", deprecated=True)
async def respond_to_legacy_assignment_request(
    request_id: str,
    payload: LegacyAssignmentResponseRequest,
    db: AsyncSession = Depends(get_db),
):
    assignment_request = await respond_to_assignment_request(
        db,
        request_id,
        AssignmentResponseRequest(response=payload.status, response_note=payload.reason),
    )
    return {"status": "success", "requestId": assignment_request.request_id, "statusValue": assignment_request.status}


@legacy_router.post("/notifications", deprecated=True)
async def create_legacy_notification_record(
    payload: LegacyNotificationCreateRequest,
    db: AsyncSession = Depends(get_db),
):
    result = await create_legacy_notification(
        db,
        recipient_id=payload.recipientId,
        notification_type=payload.notificationType,
        message=payload.message,
        idempotency_key=payload.idempotencyKey,
    )
    return notification_to_legacy_dict(result.notification)


@legacy_router.get("/notifications", deprecated=True)
async def get_legacy_notifications(db: AsyncSession = Depends(get_db)):
    result = await list_notifications(db, page=1, page_size=100)
    return [notification_to_legacy_dict(item) for item in result.notifications]


@legacy_router.get("/notifications/{notification_id}", deprecated=True)
async def get_legacy_notification(notification_id: str, db: AsyncSession = Depends(get_db)):
    notification = await get_notification(db, notification_id)
    return notification_to_legacy_dict(notification)


    get_failure_mode,
