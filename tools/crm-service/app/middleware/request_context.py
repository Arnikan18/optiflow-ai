import uuid
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id
        
        run_id = request.headers.get("X-Run-ID")
        request.state.run_id = run_id
        
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response
