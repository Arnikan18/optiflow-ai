from datetime import date
from decimal import Decimal

from sqlalchemy.orm import Session

from app.database.models import Customer


def build_seed_customers() -> list[Customer]:
    return [
        Customer(
            customer_id="CUS-ALPHA",
            name="Alpha Bank",
            tier="Enterprise",
            arr=Decimal("600000.00"),
            renewal_date=date(2026, 9, 22),
            active=True,
        ),
        Customer(
            customer_id="CUS-NOVA",
            name="Nova Retail",
            tier="Enterprise",
            arr=Decimal("1200000.00"),
            renewal_date=date(2026, 11, 20),
            active=True,
        ),
        Customer(
            customer_id="CUS-GREEN",
            name="GreenLogistics",
            tier="Standard",
            arr=Decimal("180000.00"),
            renewal_date=date(2026, 7, 27),
            active=True,
        ),
        Customer(
            customer_id="CUS-MEDI",
            name="MediCore",
            tier="Premium",
            arr=Decimal("400000.00"),
            renewal_date=date(2027, 2, 15),
            active=True,
        ),
        Customer(
            customer_id="CUS-ORBIT",
            name="Orbit Telecom",
            tier="Enterprise",
            arr=Decimal("850000.00"),
            renewal_date=date(2026, 8, 18),
            active=True,
        ),
        Customer(
            customer_id="CUS-HARBOR",
            name="Harbor Health",
            tier="Premium",
            arr=Decimal("320000.00"),
            renewal_date=date(2026, 10, 12),
            active=True,
        ),
        Customer(
            customer_id="CUS-SUMMIT",
            name="Summit Education",
            tier="Standard",
            arr=Decimal("95000.00"),
            renewal_date=date(2027, 1, 30),
            active=True,
        ),
        Customer(
            customer_id="CUS-DORMANT",
            name="Dormant Systems",
            tier="Standard",
            arr=Decimal("25000.00"),
            renewal_date=date(2025, 12, 1),
            active=False,
        ),
    ]


def seed_customers(db: Session) -> int:
    if db.query(Customer).first():
        return 0

    customers = build_seed_customers()
    db.add_all(customers)
    db.commit()
    return len(customers)
