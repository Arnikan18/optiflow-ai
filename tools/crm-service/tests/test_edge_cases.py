from sqlalchemy.exc import SQLAlchemyError

from app.database import session as database_session


def assert_error(response, status_code, error_code):
    assert response.status_code == status_code
    body = response.json()
    assert body["success"] is False
    assert body["errorCode"] == error_code
    assert "timestamp" in body
    assert "traceback" not in str(body).lower()
    return body


def test_customer_api_requires_tool_token(client):
    response = client.get("/crm/api/v1/customers")
    assert_error(response, 401, "CRM_401")


def test_invalid_list_queries_use_standard_422_shape(client, auth_headers):
    invalid_page = client.get("/crm/api/v1/customers?page=0", headers=auth_headers)
    assert_error(invalid_page, 422, "CRM_422")

    invalid_size = client.get("/crm/api/v1/customers?page_size=101", headers=auth_headers)
    assert_error(invalid_size, 422, "CRM_422")

    invalid_tier = client.get("/crm/api/v1/customers?tier=gold", headers=auth_headers)
    assert_error(invalid_tier, 422, "CRM_422")


def test_create_validation_edge_cases(client, auth_headers):
    base = {
        "customer_id": "CUS-EDGE",
        "name": "Edge Customer",
        "tier": "Standard",
        "arr": "1.00",
        "renewal_date": "2026-10-01",
    }

    cases = [
        ({**base, "customer_id": "   "}, "empty customer_id"),
        ({**base, "name": "   "}, "empty name"),
        ({**base, "tier": "Gold"}, "invalid tier"),
        ({**base, "arr": "-1.00"}, "negative arr"),
        ({**base, "arr": "1.234"}, "excessive decimal places"),
        ({**base, "renewal_date": "not-a-date"}, "invalid date"),
        ({**base, "created_at": "2026-01-01T00:00:00Z"}, "unknown field"),
    ]

    for payload, label in cases:
        response = client.post("/crm/api/v1/customers", json=payload, headers=auth_headers)
        assert_error(response, 422, "CRM_422"), label


def test_past_and_far_future_renewal_dates_are_allowed(client, auth_headers):
    past = client.post(
        "/crm/api/v1/customers",
        json={
            "customer_id": "CUS-PAST",
            "name": "Past Renewal",
            "tier": "Standard",
            "arr": "100.00",
            "renewal_date": "2020-01-01",
        },
        headers=auth_headers,
    )
    assert past.status_code == 201

    future = client.post(
        "/crm/api/v1/customers",
        json={
            "customer_id": "CUS-FUTURE",
            "name": "Future Renewal",
            "tier": "Enterprise",
            "arr": "999999999999.99",
            "renewal_date": "2099-12-31",
        },
        headers=auth_headers,
    )
    assert future.status_code == 201


def test_update_validation_and_missing_customer(client, auth_headers):
    missing = client.put(
        "/crm/api/v1/customers/CUS-MISSING",
        json={
            "name": "Missing",
            "tier": "Standard",
            "arr": "1.00",
            "renewal_date": "2026-01-01",
            "active": True,
        },
        headers=auth_headers,
    )
    assert_error(missing, 404, "CRM_404")

    invalid = client.put(
        "/crm/api/v1/customers/CUS-ALPHA",
        json={
            "name": "Alpha",
            "tier": "Unsupported",
            "arr": "1.00",
            "renewal_date": "2026-01-01",
            "active": True,
        },
        headers=auth_headers,
    )
    assert_error(invalid, 422, "CRM_422")


def test_readiness_failure_is_safe(client, monkeypatch):
    class BrokenSession:
        def execute(self, statement):
            raise SQLAlchemyError("sensitive database path")

        def close(self):
            pass

    monkeypatch.setattr(database_session, "SessionLocal", lambda: BrokenSession())
    response = client.get("/readiness")
    body = assert_error(response, 503, "CRM_503")
    assert "sensitive" not in body["message"]
