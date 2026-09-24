"""HTTP Basic Auth gate for the whole app — this dashboard is reachable from
other devices on the network (Docker binds 0.0.0.0), so it needs a password.
Username is ignored, only the password (DASHBOARD_PASSWORD) is checked.
Set DASHBOARD_PASSWORD to enable; unset it and the app is open (e.g. for
local-only dev).
"""
import base64
import os
import secrets

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

DASHBOARD_PASSWORD = os.getenv("DASHBOARD_PASSWORD")


class BasicAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if not DASHBOARD_PASSWORD:
            return await call_next(request)

        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Basic "):
            try:
                decoded = base64.b64decode(auth_header[6:]).decode("utf-8")
                _, _, password = decoded.partition(":")
            except Exception:
                password = ""
            if secrets.compare_digest(password, DASHBOARD_PASSWORD):
                return await call_next(request)

        return Response(
            status_code=401,
            headers={"WWW-Authenticate": 'Basic realm="Daybook Shubham"'},
        )
