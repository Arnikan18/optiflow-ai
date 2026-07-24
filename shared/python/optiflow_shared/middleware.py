import re
import time
import uuid
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from optiflow_shared.logging import configure_service_logging


REQUEST_ID_HEADER = "X-Request-ID"
MAX_REQUEST_ID_LENGTH = 128
_REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._:-]+$")


def sanitize_request_id(value: str | None, *, max_length: int = MAX_REQUEST_ID_LENGTH) -> str:
    if value is None:
        return str(uuid.uuid4())

    candidate = value.strip()
    if not candidate or len(candidate) > max_length:
        return str(uuid.uuid4())
    if any(ord(character) < 32 or ord(character) == 127 for character in candidate):
        return str(uuid.uuid4())
    if not _REQUEST_ID_PATTERN.fullmatch(candidate):
        return str(uuid.uuid4())
    return candidate


class RequestContextMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app,
        *,
        service_name: str,
        log_level: str | None = None,
        header_name: str = REQUEST_ID_HEADER,
        max_request_id_length: int = MAX_REQUEST_ID_LENGTH,
    ) -> None:
        super().__init__(app)
        self.service_name = service_name
        self.header_name = header_name
        self.max_request_id_length = max_request_id_length
        self.logger = configure_service_logging(service_name, log_level)

    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        request_id = sanitize_request_id(
            request.headers.get(self.header_name),
            max_length=self.max_request_id_length,
        )
        request.state.request_id = request_id
        request.state.run_id = sanitize_request_id(
            request.headers.get("X-Run-ID"),
            max_length=self.max_request_id_length,
        ) if request.headers.get("X-Run-ID") else None

        status_code = 500
        started_at = time.perf_counter()
        try:
            response = await call_next(request)
            status_code = response.status_code
            response.headers[self.header_name] = request_id
            return response
        finally:
            duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
            self.logger.info(
                "request_completed",
                extra={
                    "structured": {
                        "request_id": request_id,
                        "method": request.method,
                        "path": request.url.path,
                        "status_code": status_code,
                        "duration_ms": duration_ms,
                    }
                },
            )
