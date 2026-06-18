"""Auth middleware stub — wired into the app but bypassed when USE_AUTH=false.

To enable: set USE_AUTH=true in environment and implement token validation
inside the request block below.
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: object) -> Response:
        # Passthrough — authentication not yet implemented.
        # When USE_AUTH=true, validate the Authorization header here before
        # calling call_next(request).
        return await call_next(request)  # type: ignore[operator]
