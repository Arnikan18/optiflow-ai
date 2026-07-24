from fastapi import APIRouter, Depends, Header, Query, status
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database.session import get_db
from app.middleware.authentication import verify_tool_token
from app.schemas.requests import CustomerCreateRequest, CustomerUpdateRequest
from app.schemas.responses import CustomerListData, CustomerResponse, ResetResponseData, success_response
from app.services.customer_service import (
    CRMError,
    create_customer,
    get_customer,
    list_customers,
    reset_customers,
    update_customer,
)


router = APIRouter(
    prefix="/crm/api/v1",
    tags=["customers"],
    dependencies=[Depends(verify_tool_token)],
)
admin_router = APIRouter(tags=["admin"])


def _customer_data(customer) -> dict:
    return CustomerResponse.model_validate(customer).model_dump(mode="json")


@router.get("/customers")
def get_customers(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    active: bool | None = Query(default=None),
    tier: str | None = Query(default=None),
    search: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    result = list_customers(
        db,
        page=page,
        page_size=page_size,
        active=active,
        tier=tier,
        search=search,
    )
    data = CustomerListData(
        customers=[CustomerResponse.model_validate(customer) for customer in result.customers],
        page=result.page,
        page_size=result.page_size,
        total_items=result.total_items,
        total_pages=result.total_pages,
    )
    return success_response(data.model_dump(mode="json"))


@router.get("/customers/{customer_id}")
def get_customer_by_id(customer_id: str, db: Session = Depends(get_db)):
    customer = get_customer(db, customer_id)
    return success_response(_customer_data(customer))


@router.post("/customers", status_code=status.HTTP_201_CREATED)
def create_customer_record(payload: CustomerCreateRequest, db: Session = Depends(get_db)):
    customer = create_customer(db, payload)
    return success_response(_customer_data(customer), message="Customer created successfully")


@router.put("/customers/{customer_id}")
def update_customer_record(
    customer_id: str,
    payload: CustomerUpdateRequest,
    db: Session = Depends(get_db),
):
    customer = update_customer(db, customer_id, payload)
    return success_response(_customer_data(customer), message="Customer updated successfully")


def verify_admin_key(x_admin_key: str | None = Header(default=None, alias="X-Admin-Key")) -> None:
    settings = get_settings()
    if not settings.admin_api_key:
        raise CRMError(503, "CRM_503", "Admin reset is not configured")
    if x_admin_key != settings.admin_api_key:
        raise CRMError(401, "CRM_401", "Invalid admin credentials")


@admin_router.post("/admin/reset", dependencies=[Depends(verify_admin_key)])
def reset_crm_database(db: Session = Depends(get_db)):
    seeded_records = reset_customers(db)
    data = ResetResponseData(seeded_records=seeded_records)
    return success_response(data.model_dump(mode="json"), message="CRM database reset successfully")
