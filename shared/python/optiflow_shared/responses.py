from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

from pydantic import BaseModel


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def serialize_datetime_value(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _jsonable(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, datetime):
        return serialize_datetime_value(value)
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, list):
        return [_jsonable(item) for item in value]
    if isinstance(value, tuple):
        return [_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    return value


def success_response(data: Any, message: str = "Request completed successfully") -> dict[str, Any]:
    return {
        "success": True,
        "message": message,
        "timestamp": utc_timestamp(),
        "data": _jsonable(data),
    }


def error_response(
    message: str,
    error_code: str,
    *,
    details: list[dict[str, Any]] | None = None,
    include_details: bool = False,
) -> dict[str, Any]:
    response: dict[str, Any] = {
        "success": False,
        "message": message,
        "errorCode": error_code,
        "timestamp": utc_timestamp(),
    }
    if include_details and details:
        response["details"] = details
    return response


def validation_error_details(errors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    details: list[dict[str, Any]] = []
    for error in errors:
        location = error.get("loc", ())
        field = ".".join(str(part) for part in location if part != "body") or "request"
        details.append(
            {
                "field": field,
                "message": str(error.get("msg", "Invalid value")),
                "type": str(error.get("type", "validation_error")),
            }
        )
    return details
