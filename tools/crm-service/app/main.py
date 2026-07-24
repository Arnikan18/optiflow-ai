import contextlib
import logging

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from optiflow_shared.logging import configure_service_logging
from optiflow_shared.responses import validation_error_details

from app.api.routes import admin_router, router as customer_router
from app.config import get_settings
from app.database import session as database_session
from app.database.base import Base
from app.middleware.request_context import RequestContextMiddleware
from app.schemas.responses import error_response
from app.services.customer_service import CRMError, seed_customers_if_empty

logger = logging.getLogger("crm-service")


def initialize_database() -> None:
    Base.metadata.create_all(bind=database_session.engine)
    if not get_settings().seed_on_startup:
        return

    db = database_session.SessionLocal()
    try:
        seed_customers_if_empty(db)
    finally:
        db.close()


def _error_json(status_code: int, message: str, error_code: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=error_response(message=message, error_code=error_code),
    )


def create_app(*, initialize_on_startup: bool = True) -> FastAPI:
    settings = get_settings()
    global logger
    logger = configure_service_logging(settings.service_name, settings.log_level)

    @contextlib.asynccontextmanager
    async def lifespan(app: FastAPI):
        if initialize_on_startup:
            initialize_database()
        yield

    app = FastAPI(
        title="OptiFlow CRM Service",
        version="4.0",
        lifespan=lifespan,
    )
    app.add_middleware(RequestContextMiddleware)
    app.include_router(customer_router)
    app.include_router(admin_router)

    @app.exception_handler(CRMError)
    async def crm_error_handler(request: Request, exc: CRMError) -> JSONResponse:
        return _error_json(exc.status_code, exc.message, exc.error_code)

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        logger.info(
            "request_validation_failed",
            extra={
                "structured": {
                    "request_id": getattr(request.state, "request_id", None),
                    "validation_errors": validation_error_details(exc.errors()),
                }
            },
        )
        return _error_json(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Request validation failed",
            "CRM_422",
        )

    @app.exception_handler(HTTPException)
    async def http_error_handler(request: Request, exc: HTTPException) -> JSONResponse:
        error_code = "CRM_401" if exc.status_code == status.HTTP_401_UNAUTHORIZED else f"CRM_{exc.status_code}"
        public_message = exc.detail if isinstance(exc.detail, str) else "Request failed"
        return _error_json(exc.status_code, public_message, error_code)

    @app.exception_handler(Exception)
    async def unexpected_error_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unexpected CRM service error")
        return _error_json(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "Unexpected CRM service error",
            "CRM_500",
        )

    @app.get("/")
    def home():
        return {
            "service": "CRM Service",
            "message": "OptiFlow CRM Service is running",
            "version": "4.0",
        }

    @app.get("/health")
    def health():
        return {
            "status": "healthy",
            "service": settings.service_name,
        }

    @app.get("/readiness")
    def readiness():
        db = database_session.SessionLocal()
        try:
            db.execute(text("SELECT 1"))
            return {
                "status": "ready",
                "service": settings.service_name,
                "database": "UP",
            }
        except SQLAlchemyError:
            logger.exception("CRM database readiness check failed")
            return _error_json(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "CRM database is not ready",
                "CRM_503",
            )
        finally:
            db.close()

    return app


app = create_app()
