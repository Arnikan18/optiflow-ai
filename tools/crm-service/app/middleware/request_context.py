from app.config import get_settings
from optiflow_shared.middleware import RequestContextMiddleware as SharedRequestContextMiddleware


class RequestContextMiddleware(SharedRequestContextMiddleware):
    def __init__(self, app) -> None:
        settings = get_settings()
        super().__init__(
            app,
            service_name=settings.service_name,
            log_level=settings.log_level,
            header_name=settings.request_id_header,
            max_request_id_length=settings.max_request_id_length,
        )
