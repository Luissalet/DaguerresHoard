"""Browser-attack guard middleware: DNS-rebinding and cross-site write
protection, no CORS. Applied to every route."""
from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse


class GuardMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, port: int):
        super().__init__(app)
        self.allowed_hosts = {f"127.0.0.1:{port}", f"localhost:{port}"}
        self.port = port

    async def dispatch(self, request: Request, call_next):
        host = request.headers.get("host", "")
        if host not in self.allowed_hosts:
            return JSONResponse(
                {"error": "forbidden_host", "message": f"Host header '{host}' is not allowed (DNS rebinding guard)."},
                status_code=403,
            )
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            origin = request.headers.get("origin")
            sec_fetch_site = request.headers.get("sec-fetch-site")
            own_origins = {f"http://127.0.0.1:{self.port}", f"http://localhost:{self.port}"}
            if origin is not None and origin not in own_origins:
                return JSONResponse(
                    {"error": "forbidden_origin", "message": "Cross-origin write requests are rejected."},
                    status_code=403,
                )
            if sec_fetch_site == "cross-site":
                return JSONResponse(
                    {"error": "forbidden_origin", "message": "Cross-site write requests are rejected."},
                    status_code=403,
                )
        return await call_next(request)
