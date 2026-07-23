from sqlalchemy.orm import Session

from app.database.models import Customer


def seed_customers(db: Session) -> None:
    existing_customer = db.query(Customer).first()

    if existing_customer:
        return

    customers = [
        Customer(
            customer_id="CUST-001",
            name="Alpha Technologies",
            tier="Enterprise",
            arr=250000.00,
            renewal_date="2026-09-15",
            active=True
        ),
        Customer(
            customer_id="CUST-002",
            name="BlueWave Retail",
            tier="Premium",
            arr=120000.00,
            renewal_date="2026-11-20",
            active=True
        ),
        Customer(
            customer_id="CUST-003",
            name="Ceylon Logistics",
            tier="Standard",
            arr=60000.00,
            renewal_date="2027-01-10",
            active=True
        )
    ]

    db.add_all(customers)
    db.commit()