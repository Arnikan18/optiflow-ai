import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any


VALID_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
_HANDLER_MARKER = "_optiflow_structured_handler"


def _utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class StructuredJsonFormatter(logging.Formatter):
    def __init__(self, service_name: str) -> None:
        super().__init__()
        self.service_name = service_name

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": _utc_timestamp(),
            "level": record.levelname,
            "service_name": self.service_name,
            "message": record.getMessage(),
        }
        structured = getattr(record, "structured", None)
        if isinstance(structured, dict):
            payload.update(structured)
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str, separators=(",", ":"))


def normalize_log_level(log_level: str | None) -> str:
    candidate = (log_level or "INFO").strip().upper()
    return candidate if candidate in VALID_LOG_LEVELS else "INFO"


def configure_service_logging(service_name: str, log_level: str | None = None) -> logging.Logger:
    logger = logging.getLogger(service_name)
    logger.setLevel(getattr(logging, normalize_log_level(log_level)))
    logger.propagate = False

    if not any(getattr(handler, _HANDLER_MARKER, False) for handler in logger.handlers):
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(StructuredJsonFormatter(service_name))
        setattr(handler, _HANDLER_MARKER, True)
        logger.addHandler(handler)

    return logger
