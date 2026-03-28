"""
FastForge Identity Module
=============================
Pre-built user/role/auth system. 

Usage in your main.py:

    from fastforge_core.auth import JwtService, TokenConfig, AuthMiddleware
    from fastforge_core.modules.identity import create_identity_router

    jwt_service = JwtService(TokenConfig(secret=settings.JWT_SECRET))
    app.add_middleware(AuthMiddleware, jwt_service=jwt_service)
    app.include_router(
        create_identity_router(jwt_service, get_db=get_db),
        prefix="/api/v1/auth",
    )
"""
from .router import create_identity_router
from .models import User, Role
from .service import IdentityService
from .schemas import (
    LoginRequest, RegisterRequest, TokenResponse, RefreshRequest,
    UserResponse, UserUpdate, ChangePasswordRequest,
    RoleCreate, RoleUpdate, RoleResponse,
)

__all__ = [
    "create_identity_router",
    "User", "Role", "IdentityService",
    "LoginRequest", "RegisterRequest", "TokenResponse",
    "UserResponse", "RoleCreate", "RoleResponse",
]
