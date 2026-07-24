from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, Query, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database.models import FailureMode
from app.database.session import get_db
from app.middleware.authentication import verify_tool_token
from app.schemas.requests import (
    AdminConfiguredResponseRequest,
    AssignmentRequestCreateRequest,
    AssignmentResponseRequest,
    LegacyAssignmentCreateRequest,
    LegacyAssignmentResponseRequest,
    LegacyNotificationCreateRequest,
    NotificationCreateRequest,
)
from app.schemas.responses import (
    AssignmentRequestListData,
    AssignmentRequestResponse,
    NotificationListData,
    NotificationResponse,
    ResetResponseData,
    success_response,
)
from app.services.assignment_service import (
    CommunicationError,
    assignment_to_legacy_dict,
    configure_legacy_response,
    create_assignment_request,
    create_legacy_assignment_request,
    get_assignment_request,
    list_assignment_requests,
    reset_communication,
    respond_to_assignment_request,
)
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
    db: AsyncSession = Depends(get_db),
):
    assignment_request = await create_assignment_request(db, payload)
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
    assignment_request = await get_assignment_request(db, request_id)
    return success_response(_assignment_data(assignment_request))


@router.post("/assignment-requests/{request_id}/respond")
async def respond_to_assignment_request_record(
    request_id: str,
    payload: AssignmentResponseRequest,
    db: AsyncSession = Depends(get_db),
):
    assignment_request = await respond_to_assignment_request(db, request_id, payload)
    return success_response(_assignment_data(assignment_request), message="Assignment response recorded successfully")


@router.post("/notifications", status_code=201)
async def create_notification_record(
    payload: NotificationCreateRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
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


@legacy_router.post("/admin/next-response", deprecated=True)
async def configure_next_response(payload: AdminConfiguredResponseRequest, db: AsyncSession = Depends(get_db)):
    configured = await configure_legacy_response(
        db,
        specialist_id=payload.specialistId,
        status=payload.status,
        reason=payload.reason,
        delay_ms=payload.delayMs,
    )
    return {
        "status": "success",
        "specialistId": configured.specialist_id,
        "nextStatus": configured.next_status,
    }


@legacy_router.post("/admin/failure-mode", deprecated=True)
async def configure_failure_mode(data: dict, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(FailureMode).limit(1))
    fm = result.scalar_one_or_none()
    if not fm:
        fm = FailureMode(mode=data.get("mode", "TIMEOUT"), enabled=0, updated_at="")

    fm.mode = data.get("mode", "TIMEOUT")
    fm.enabled = 1 if data.get("enabled", False) else 0
    fm.delay_ms = data.get("delayMs", 5000)
    fm.remaining_failures = data.get("failureCount", 2)
    fm.updated_at = datetime.now(timezone.utc).isoformat()
    db.add(fm)
    await db.commit()
    return {"status": "success", "mode": fm.mode, "enabled": bool(fm.enabled)}
