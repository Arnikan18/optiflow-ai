from typing import Optional
from sqlalchemy import String, Integer
from sqlalchemy.orm import Mapped, mapped_column
from app.database.base import Base

class Customer(Base):
    __tablename__ = "customers"
    customer_id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    tier: Mapped[str] = mapped_column(String, nullable=False)
    annual_recurring_revenue: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    renewal_date: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    account_owner: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    strategic_account: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    relationship_status: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    industry: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[str] = mapped_column(String, nullable=False)
    updated_at: Mapped[str] = mapped_column(String, nullable=False)
    scenario_id: Mapped[str] = mapped_column(String, nullable=False)

class CommercialDependency(Base):
    __tablename__ = "commercial_dependencies"
    dependency_id: Mapped[str] = mapped_column(String, primary_key=True)
    customer_id: Mapped[str] = mapped_column(String, nullable=False)
    dependency_type: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    due_at: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    impact_level: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    created_at: Mapped[str] = mapped_column(String, nullable=False)
    updated_at: Mapped[str] = mapped_column(String, nullable=False)

class FailureMode(Base):
    __tablename__ = "failure_modes"
    mode_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    mode: Mapped[str] = mapped_column(String, nullable=False)
    enabled: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    delay_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    remaining_failures: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    updated_at: Mapped[str] = mapped_column(String, nullable=False)
