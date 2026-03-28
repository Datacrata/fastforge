"""
FastForge Audit Logging Middleware
=====================================
automatic audit logging.
Logs who did what, when, and how long it took.
"""
from __future__ import annotations
import time
import logging
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("fastforge.audit")


class AuditLogMiddleware(BaseHTTPMiddleware):
    """
    Logs every request with user, method, path, status, and duration.

    Add to your app:
        app.add_middleware(AuditLogMiddleware)
    """

    async def dispatch(self, request: Request, call_next):
        start = time.time()

        # Extract user info if available
        user_id = getattr(request.state, "user_id", "anonymous") if hasattr(request, "state") else "anonymous"

        response = await call_next(request)

        duration_ms = round((time.time() - start) * 1000, 2)

        # Only log mutating operations by default
        if request.method in ("POST", "PUT", "PATCH", "DELETE"):
            logger.info(
                "AUDIT | %s | %s %s | %d | %sms",
                user_id,
                request.method,
                request.url.path,
                response.status_code,
                duration_ms,
            )

        return response
