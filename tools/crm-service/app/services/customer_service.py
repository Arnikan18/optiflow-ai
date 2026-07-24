from dataclasses import dataclass
from math import ceil
from typing import Optional

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.database.models import Customer
from app.database.seed import build_seed_customers
from app.schemas.requests import (
    CustomerCreateRequest,
    CustomerUpdateRequest,
    normalize_customer_id,
    normalize_search,
    normalize_tier,
)


class CRMError(Exception):
    def __init__(self, status_code: int, error_code: str, message: str) -> None:
        self.status_code = status_code
        self.error_code = error_code
        self.message = message
        super().__init__(message)


@dataclass(frozen=True)
class CustomerListResult:
    customers: list[Customer]
    page: int
    page_size: int
    total_items: int
    total_pages: int


def _database_error() -> CRMError:
    return CRMError(503, "CRM_503", "CRM database operation failed")


def list_customers(
    db: Session,
    *,
    page: int,
    page_size: int,
    active: Optional[bool] = None,
    tier: Optional[str] = None,
    search: Optional[str] = None,
) -> CustomerListResult:
    conditions = []

    if active is not None:
        conditions.append(Customer.active.is_(active))

    if tier is not None:
        try:
            conditions.append(Customer.tier == normalize_tier(tier))
        except ValueError as exc:
            raise CRMError(422, "CRM_422", str(exc)) from exc

    normalized_search = normalize_search(search)
    if normalized_search:
        pattern = f"%{normalized_search}%"
        conditions.append(
            or_(
                Customer.customer_id.ilike(pattern),
                Customer.name.ilike(pattern),
            )
        )

    try:
        total_items = db.scalar(select(func.count(Customer.id)).where(*conditions)) or 0
        total_pages = ceil(total_items / page_size) if total_items else 0
        customers = list(
            db.scalars(
                select(Customer)
                .where(*conditions)
                .order_by(Customer.customer_id)
                .offset((page - 1) * page_size)
                .limit(page_size)
            )
        )
    except SQLAlchemyError as exc:
        raise _database_error() from exc

    return CustomerListResult(
        customers=customers,
        page=page,
        page_size=page_size,
        total_items=total_items,
        total_pages=total_pages,
    )


def get_customer(db: Session, customer_id: str) -> Customer:
    try:
        normalized_id = normalize_customer_id(customer_id)
    except ValueError as exc:
        raise CRMError(422, "CRM_422", str(exc)) from exc

    try:
        customer = db.scalar(select(Customer).where(Customer.customer_id == normalized_id))
    except SQLAlchemyError as exc:
        raise _database_error() from exc

    if customer is None:
        raise CRMError(404, "CRM_404", "Customer not found")
    return customer


def create_customer(db: Session, payload: CustomerCreateRequest) -> Customer:
    customer = Customer(**payload.model_dump())
    try:
        db.add(customer)
        db.commit()
        db.refresh(customer)
        return customer
    except IntegrityError as exc:
        db.rollback()
        raise CRMError(409, "CRM_409", "Customer identifier already exists") from exc
    except SQLAlchemyError as exc:
        db.rollback()
        raise _database_error() from exc


def update_customer(db: Session, customer_id: str, payload: CustomerUpdateRequest) -> Customer:
    customer = get_customer(db, customer_id)
    for field, value in payload.model_dump().items():
        setattr(customer, field, value)

    try:
        db.add(customer)
        db.commit()
        db.refresh(customer)
        return customer
    except SQLAlchemyError as exc:
        db.rollback()
        raise _database_error() from exc


def seed_customers_if_empty(db: Session) -> int:
    try:
        existing = db.scalar(select(func.count(Customer.id))) or 0
        if existing:
            return 0
        customers = build_seed_customers()
        db.add_all(customers)
        db.commit()
        return len(customers)
    except SQLAlchemyError as exc:
        db.rollback()
        raise _database_error() from exc


def reset_customers(db: Session) -> int:
    try:
        db.query(Customer).delete()
        customers = build_seed_customers()
        db.add_all(customers)
        db.commit()
        return len(customers)
    except SQLAlchemyError as exc:
        db.rollback()
        raise _database_error() from exc
