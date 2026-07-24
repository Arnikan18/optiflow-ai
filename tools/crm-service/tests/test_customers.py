from datetime import date
from decimal import Decimal

from app.database import session as database_session
from app.database.models import Customer
from app.database.seed import seed_customers
from app.services.customer_service import seed_customers_if_empty


def assert_success(response):
    body = response.json()
    assert body["success"] is True
    assert "timestamp" in body
    return body["data"]


def test_health_and_readiness_succeed(client):
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json() == {"status": "healthy", "service": "crm-service"}

    readiness = client.get("/readiness")
    assert readiness.status_code == 200
    assert readiness.json()["database"] == "UP"


def test_customer_list_default_pagination_and_stable_metadata(client, auth_headers):
    response = client.get("/crm/api/v1/customers", headers=auth_headers)
    assert response.status_code == 200
    data = assert_success(response)
    assert data["page"] == 1
    assert data["page_size"] == 20
    assert data["total_items"] == 5
    assert data["total_pages"] == 1
    assert [customer["customer_id"] for customer in data["customers"]] == sorted(
        customer["customer_id"] for customer in data["customers"]
    )


def test_customer_list_custom_pagination_and_page_beyond_results(client, auth_headers):
    page_one = client.get("/crm/api/v1/customers?page=1&page_size=2", headers=auth_headers)
    assert page_one.status_code == 200
    data = assert_success(page_one)
    assert len(data["customers"]) == 2
    assert data["total_pages"] == 3

    beyond = client.get("/crm/api/v1/customers?page=99&page_size=2", headers=auth_headers)
    assert beyond.status_code == 200
    data = assert_success(beyond)
    assert data["customers"] == []
    assert data["page"] == 99


def test_customer_filters_and_search(client, auth_headers):
    active = client.get("/crm/api/v1/customers?active=false", headers=auth_headers)
    assert active.status_code == 200
    active_data = assert_success(active)
    assert active_data["total_items"] == 1
    assert active_data["customers"][0]["active"] is False

    tier = client.get("/crm/api/v1/customers?tier= enterprise ", headers=auth_headers)
    assert tier.status_code == 200
    tier_data = assert_success(tier)
    assert tier_data["total_items"] == 2
    assert all(customer["tier"] == "Enterprise" for customer in tier_data["customers"])

    by_id = client.get("/crm/api/v1/customers?search=alpha", headers=auth_headers)
    assert by_id.status_code == 200
    assert assert_success(by_id)["customers"][0]["customer_id"] == "CUS-ALPHA"

    no_match = client.get("/crm/api/v1/customers?search=missing", headers=auth_headers)
    assert no_match.status_code == 200
    assert assert_success(no_match)["customers"] == []


def test_get_existing_missing_and_inactive_customer(client, auth_headers):
    existing = client.get("/crm/api/v1/customers/cus-alpha", headers=auth_headers)
    assert existing.status_code == 200
    assert assert_success(existing)["customer_id"] == "CUS-ALPHA"

    inactive = client.get("/crm/api/v1/customers/CUS-DORMANT", headers=auth_headers)
    assert inactive.status_code == 200
    assert assert_success(inactive)["active"] is False

    missing = client.get("/crm/api/v1/customers/CUS-MISSING", headers=auth_headers)
    assert missing.status_code == 404
    assert missing.json()["errorCode"] == "CRM_404"


def test_create_customer_defaults_normalizes_and_rejects_duplicates(client, auth_headers):
    payload = {
        "customer_id": " cust-new ",
        "name": " New Customer ",
        "tier": "premium",
        "arr": "0.00",
        "renewal_date": "2026-10-01",
    }
    created = client.post("/crm/api/v1/customers", json=payload, headers=auth_headers)
    assert created.status_code == 201
    data = assert_success(created)
    assert data["customer_id"] == "CUST-NEW"
    assert data["name"] == "New Customer"
    assert data["tier"] == "Premium"
    assert data["arr"] == "0.00"
    assert data["active"] is True

    duplicate = client.post("/crm/api/v1/customers", json=payload, headers=auth_headers)
    assert duplicate.status_code == 409
    assert duplicate.json()["errorCode"] == "CRM_409"

    after_duplicate = client.post(
        "/crm/api/v1/customers",
        json={
            "customer_id": "CUST-UNIQUE",
            "name": "Unique Customer",
            "tier": "Standard",
            "arr": "10.00",
            "renewal_date": "2026-12-01",
        },
        headers=auth_headers,
    )
    assert after_duplicate.status_code == 201


def test_update_customer_preserves_created_at_and_changes_updated_at(client, auth_headers):
    before = assert_success(client.get("/crm/api/v1/customers/CUS-GREEN", headers=auth_headers))
    response = client.put(
        "/crm/api/v1/customers/CUS-GREEN",
        json={
            "name": "Green Logistics Updated",
            "tier": "enterprise",
            "arr": "250000.00",
            "renewal_date": "2026-08-01",
            "active": False,
        },
        headers=auth_headers,
    )
    assert response.status_code == 200
    updated = assert_success(response)
    assert updated["name"] == "Green Logistics Updated"
    assert updated["tier"] == "Enterprise"
    assert updated["active"] is False
    assert updated["created_at"] == before["created_at"]
    assert updated["updated_at"] >= before["updated_at"]


def test_seed_is_idempotent_and_does_not_overwrite_existing_data(client, auth_headers):
    db = database_session.SessionLocal()
    try:
        added = seed_customers(db)
        assert added == 0
        db.add(
            Customer(
                customer_id="CUS-LOCAL",
                name="Local Customer",
                tier="Standard",
                arr=Decimal("1.00"),
                renewal_date=date(2026, 1, 1),
                active=True,
            )
        )
        db.commit()
        assert seed_customers_if_empty(db) == 0
    finally:
        db.close()

    response = client.get("/crm/api/v1/customers/CUS-LOCAL", headers=auth_headers)
    assert response.status_code == 200


def test_admin_reset_requires_key_and_restores_seed(client, auth_headers, admin_headers, monkeypatch):
    client.post(
        "/crm/api/v1/customers",
        json={
            "customer_id": "CUS-TEMP",
            "name": "Temporary Customer",
            "tier": "Standard",
            "arr": "10.00",
            "renewal_date": "2026-12-01",
        },
        headers=auth_headers,
    )

    missing = client.post("/admin/reset")
    assert missing.status_code == 401
    assert missing.json()["errorCode"] == "CRM_401"

    invalid = client.post("/admin/reset", headers={"X-Admin-Key": "wrong"})
    assert invalid.status_code == 401
    assert invalid.json()["errorCode"] == "CRM_401"

    reset = client.post("/admin/reset", headers=admin_headers)
    assert reset.status_code == 200
    assert assert_success(reset)["seeded_records"] == 5

    second_reset = client.post("/admin/reset", headers=admin_headers)
    assert second_reset.status_code == 200
    assert assert_success(second_reset)["seeded_records"] == 5

    missing_after_reset = client.get("/crm/api/v1/customers/CUS-TEMP", headers=auth_headers)
    assert missing_after_reset.status_code == 404

    from app.config import get_settings

    monkeypatch.delenv("ADMIN_API_KEY", raising=False)
    get_settings.cache_clear()
    disabled = client.post("/admin/reset", headers=admin_headers)
    assert disabled.status_code == 503
    assert disabled.json()["errorCode"] == "CRM_503"
