import contextlib
import logging
from collections.abc import AsyncIterator

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.api.routes import admin_router, legacy_router, router
from app.config import get_settings
from app.database import session as db_session
from app.database.base import Base
from app.database.seed import seed_workforce_if_empty
from app.middleware.request_context import RequestContextMiddleware
from app.schemas.responses import error_response
from app.services.specialist_service import WorkforceError


logger = logging.getLogger(__name__)


def _error_json(status_code: int, message: str, error_code: str) -> JSONResponse:
    return JSONResponse(status_code=status_code, content=error_response(message, error_code))


async def initialize_database() -> None:
    async with db_session.engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    if get_settings().seed_on_startup:
        async with db_session.async_session() as session:
            await seed_workforce_if_empty(session)


def create_app(*, initialize_on_startup: bool = True) -> FastAPI:
    @contextlib.asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        if initialize_on_startup:
            await initialize_database()
        yield
        await db_session.engine.dispose()

    application = FastAPI(
        title="OptiFlow Workforce Service",
        version="4.0",
        lifespan=lifespan,
    )
    application.add_middleware(RequestContextMiddleware)
    application.include_router(router)
    application.include_router(admin_router)
    application.include_router(legacy_router)

    @application.exception_handler(WorkforceError)
    async def workforce_error_handler(_: Request, exc: WorkforceError) -> JSONResponse:
        return _error_json(exc.status_code, exc.message, exc.error_code)

    @application.exception_handler(RequestValidationError)
    async def validation_error_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
        logger.info("Workforce request validation failed: %s", exc.errors())
        return _error_json(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Request validation failed",
            "WORKFORCE_422",
        )

    @application.exception_handler(HTTPException)
    async def http_error_handler(_: Request, exc: HTTPException) -> JSONResponse:
        error_code = (
            "WORKFORCE_401" if exc.status_code == status.HTTP_401_UNAUTHORIZED else f"WORKFORCE_{exc.status_code}"
        )
        public_message = "Workforce service error" if exc.status_code >= 500 else str(exc.detail)
        return _error_json(exc.status_code, public_message, error_code)

    @application.exception_handler(Exception)
    async def unexpected_error_handler(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unexpected Workforce service error: %s", exc)
        return _error_json(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "Workforce service encountered an unexpected error",
            "WORKFORCE_500",
        )

    @application.get("/")
    async def root():
        settings = get_settings()
        return {"service": settings.service_name, "version": "4.0"}

    @application.get("/health")
    async def health():
        return {"status": "healthy", "service": get_settings().service_name}

    @application.get("/readiness")
    async def readiness():
        try:
            async with db_session.async_session() as session:
                await session.execute(text("SELECT 1"))
            return {
                "status": "ready",
                "service": get_settings().service_name,
                "database": "reachable",
            }
        except SQLAlchemyError as exc:
            logger.exception("Workforce readiness database failure: %s", exc)
            return _error_json(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "Workforce database is not reachable",
                "WORKFORCE_503",
            )

    return application


app = create_app()
