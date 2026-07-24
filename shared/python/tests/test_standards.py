import json
import logging
import re
from datetime import datetime

from fastapi import FastAPI
from fastapi.testclient import TestClient

from optiflow_shared.errors import ServiceError
from optiflow_shared.logging import configure_service_logging
from optiflow_shared.middleware import REQUEST_ID_HEADER, RequestContextMiddleware, sanitize_request_id
from optiflow_shared.responses import error_response, success_response, utc_timestamp, validation_error_details


def test_utc_timestamp_uses_zulu_time() -> None:
    timestamp = utc_timestamp()

    assert timestamp.endswith("Z")
    datetime.fromisoformat(timestamp.replace("Z", "+00:00"))


def test_success_and_error_response_shapes() -> None:
    success = success_response({"customer_id": "CUS-1"}, "Found")
    error = error_response("Missing", "CRM_404")

    assert success["success"] is True
    assert success["message"] == "Found"
    assert success["data"] == {"customer_id": "CUS-1"}
    assert re.fullmatch(r".+Z", success["timestamp"])
    assert error["success"] is False
    assert error["errorCode"] == "CRM_404"
    assert "requestId" not in error
    assert "details" not in error


def test_error_response_can_include_validation_details_when_enabled() -> None:
    details = validation_error_details(
        [
            {
                "loc": ("body", "customer_id"),
                "msg": "Field required",
                "type": "missing",
            }
        ]
    )

    response = error_response("Request validation failed", "CRM_422", details=details, include_details=True)

    assert response["details"] == [{"field": "customer_id", "message": "Field required", "type": "missing"}]


def test_service_error_exposes_standard_fields() -> None:
    exc = ServiceError(409, "INCIDENT_409", "Conflict", retryable=False)

    assert exc.status_code == 409
    assert exc.error_code == "INCIDENT_409"
    assert exc.public_message == "Conflict"
    assert exc.message == "Conflict"
    assert exc.retryable is False


def test_request_id_sanitizer_preserves_valid_ids_and_replaces_invalid_values() -> None:
    preserved = "run-2026_07:24.request-1"
    generated_for_missing = sanitize_request_id(None)
    generated_for_control_char = sanitize_request_id("bad\nid")
    generated_for_long_value = sanitize_request_id("x" * 129)

    assert sanitize_request_id(preserved) == preserved
    for request_id in (generated_for_missing, generated_for_control_char, generated_for_long_value):
        assert len(request_id) == 36
        assert request_id.count("-") == 4


def test_request_context_middleware_returns_header_and_structured_log(capsys) -> None:
    app = FastAPI()
    app.add_middleware(RequestContextMiddleware, service_name="shared-test-service", log_level="INFO")

    @app.get("/health")
    async def health():
        return {"status": "healthy"}

    supplied_request_id = "req-123"
    response = TestClient(app).get("/health", headers={REQUEST_ID_HEADER: supplied_request_id})

    assert response.status_code == 200
    assert response.headers[REQUEST_ID_HEADER] == supplied_request_id
    log_line = capsys.readouterr().out.strip().splitlines()[-1]
    log_record = json.loads(log_line)
    assert log_record["service_name"] == "shared-test-service"
    assert log_record["request_id"] == supplied_request_id
    assert log_record["method"] == "GET"
    assert log_record["path"] == "/health"
    assert log_record["status_code"] == 200


def test_logging_configuration_is_idempotent() -> None:
    logger = configure_service_logging("shared-idempotent-test", "not-a-level")
    handler_count = len(logger.handlers)
    same_logger = configure_service_logging("shared-idempotent-test", "DEBUG")

    assert logger is same_logger
    assert len(same_logger.handlers) == handler_count
    assert same_logger.level == logging.DEBUG
