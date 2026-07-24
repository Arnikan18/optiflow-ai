import contextlib
import logging
from collections.abc import AsyncIterator

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from optiflow_shared.logging import configure_service_logging
from optiflow_shared.responses import validation_error_details

from app.api.routes import admin_router, legacy_router, router
from app.config import get_settings
from app.database import session as db_session
from app.database.base import Base
from app.middleware.request_context import RequestContextMiddleware
from app.schemas.responses import error_response
from app.services.incident_service import IncidentError, seed_incidents_if_empty


logger = logging.getLogger(__name__)


def _error_json(status_code: int, message: str, error_code: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content=error_response(message, error_code),
    )


async def initialize_database() -> None:
    async with db_session.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    if get_settings().seed_on_startup:
        async with db_session.async_session() as session:
            await seed_incidents_if_empty(session)


def create_app(*, initialize_on_startup: bool = True) -> FastAPI:
    settings = get_settings()
    global logger
    logger = configure_service_logging(settings.service_name, settings.log_level)

    @contextlib.asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        if initialize_on_startup:
            await initialize_database()
        yield
        await db_session.engine.dispose()

    application = FastAPI(
        title="OptiFlow Incident Service",
        version="4.0",
        lifespan=lifespan,
    )
    application.add_middleware(RequestContextMiddleware)

    application.include_router(router)
    application.include_router(admin_router)
    application.include_router(legacy_router)

    @application.exception_handler(IncidentError)
    async def incident_error_handler(_: Request, exc: IncidentError) -> JSONResponse:
        return _error_json(exc.status_code, exc.message, exc.error_code)

    @application.exception_handler(RequestValidationError)
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
            "INCIDENT_422",
        )

    @application.exception_handler(HTTPException)
    async def http_error_handler(_: Request, exc: HTTPException) -> JSONResponse:
        error_code = "INCIDENT_401" if exc.status_code == status.HTTP_401_UNAUTHORIZED else f"INCIDENT_{exc.status_code}"
        public_message = "Incident service error" if exc.status_code >= 500 else str(exc.detail)
        return _error_json(exc.status_code, public_message, error_code)

    @application.exception_handler(Exception)
    async def unexpected_error_handler(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unexpected Incident service error: %s", exc)
        return _error_json(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "Incident service encountered an unexpected error",
            "INCIDENT_500",
        )

    @application.get("/")
    async def root():
        return {"service": settings.service_name, "version": "4.0"}

    @application.get("/health")
    async def health():
        return {
            "status": "healthy",
            "service": settings.service_name,
        }

    @application.get("/readiness")
    async def readiness():
        try:
            async with db_session.async_session() as session:
                await session.execute(text("SELECT 1"))
            return {
                "status": "ready",
                "service": settings.service_name,
                "database": "reachable",
            }
        except SQLAlchemyError as exc:
            logger.exception("Incident readiness database failure: %s", exc)
            return _error_json(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "Incident database is not reachable",
                "INCIDENT_503",
            )

    return application


app = create_app()
