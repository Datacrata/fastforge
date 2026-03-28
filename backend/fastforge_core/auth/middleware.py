"""
FastForge Auth Middleware
============================
Extracts JWT from Authorization header on every request and populates:
  - request.state.user_id
  - request.state.email
  - request.state.roles       (set)
  - request.state.permissions  (set)
  - request.state.tenant_id
  - request.state.is_authenticated

This is what makes @require_permission and GenericRepository's
multi-tenant filtering work automatically.
"""
from __future__ import annotations
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from .jwt_service import JwtService
import logging

logger = logging.getLogger("fastforge.auth")


class AuthMiddleware(BaseHTTPMiddleware):
    """
    JWT authentication middleware.
    Populates request.state with user context from the token.
    Does NOT reject unauthenticated requests — that's the job of
    @require_permission or Depends(get_current_user).

    Usage:
        jwt_service = JwtService(config)
        app.add_middleware(AuthMiddleware, jwt_service=jwt_service)
    """

    def __init__(self, app, jwt_service: JwtService):
        super().__init__(app)
        self.jwt_service = jwt_service

    async def dispatch(self, request: Request, call_next):
        # Set defaults
        request.state.user_id = None
        request.state.email = None
        request.state.roles = set()
        request.state.permissions = set()
        request.state.tenant_id = None
        request.state.is_authenticated = False

        # Extract token
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
            payload = self.jwt_service.decode_token(token)

            if payload and payload.token_type == "access":
                request.state.user_id = payload.sub
                request.state.email = payload.email
                request.state.roles = set(payload.roles)
                request.state.permissions = set(payload.permissions)
                request.state.tenant_id = payload.tenant_id
                request.state.is_authenticated = True

        # Also check for tenant from header (__tenant header)
        tenant_header = request.headers.get("__tenant") or request.headers.get("X-Tenant-Id")
        if tenant_header and not request.state.tenant_id:
            request.state.tenant_id = tenant_header

        response = await call_next(request)
        return response


# ─── FastAPI Dependencies ────────────────────────────────────────────────────

def get_current_user(request: Request) -> dict:
    """
    FastAPI dependency — returns current user info or raises 401.

    Usage:
        @router.get("/me")
        def get_me(user = Depends(get_current_user)):
            return user
    """
    if not request.state.is_authenticated:
        from fastapi import HTTPException, status
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return {
        "user_id": request.state.user_id,
        "email": request.state.email,
        "roles": list(request.state.roles),
        "permissions": list(request.state.permissions),
        "tenant_id": request.state.tenant_id,
    }


def get_current_user_id(request: Request) -> str:
    """FastAPI dependency — returns current user ID or raises 401."""
    user = get_current_user(request)
    return user["user_id"]


def get_optional_user(request: Request) -> dict | None:
    """FastAPI dependency — returns user info or None (no 401)."""
    if request.state.is_authenticated:
        return {
            "user_id": request.state.user_id,
            "email": request.state.email,
            "roles": list(request.state.roles),
            "permissions": list(request.state.permissions),
            "tenant_id": request.state.tenant_id,
        }
    return None


def get_tenant_id(request: Request) -> str | None:
    """FastAPI dependency — returns current tenant ID."""
    return request.state.tenant_id
