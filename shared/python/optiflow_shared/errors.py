from typing import Optional

from pydantic import BaseModel


class ServiceError(Exception):
    """Public service exception shape shared by OptiFlow HTTP tools."""

    def __init__(
        self,
        status_code: int,
        error_code: str,
        public_message: str,
        *,
        retryable: bool = False,
    ) -> None:
        self.status_code = status_code
        self.error_code = error_code
        self.public_message = public_message
        self.message = public_message
        self.retryable = retryable
        super().__init__(public_message)


class ErrorDetail(BaseModel):
    code: str
    message: str
    retryable: bool = False
    service: str
    requestId: Optional[str] = None

class ErrorResponse(BaseModel):
    error: ErrorDetail

# Standard error codes
VALIDATION_ERROR = "VALIDATION_ERROR"
NOT_FOUND = "NOT_FOUND"
UNAUTHORISED = "UNAUTHORISED"
FORBIDDEN = "FORBIDDEN"
CONFLICT = "CONFLICT"
RATE_LIMITED = "RATE_LIMITED"
SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"
FAILURE_MODE_ACTIVE = "FAILURE_MODE_ACTIVE"
DATABASE_ERROR = "DATABASE_ERROR"
INTERNAL_ERROR = "INTERNAL_ERROR"
STALE_PLAN = "STALE_PLAN"
NO_FEASIBLE_PLAN = "NO_FEASIBLE_PLAN"
APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
APPROVAL_EXPIRED = "APPROVAL_EXPIRED"
EXECUTION_PARTIAL_FAILURE = "EXECUTION_PARTIAL_FAILURE"
