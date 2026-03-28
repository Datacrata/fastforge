"""
FastForge Identity Router
==============================
Pre-built auth endpoints. Mount this in your app:

    from fastforge_core.modules.identity import create_identity_router
    app.include_router(create_identity_router(jwt_service), prefix="/api/v1/auth")
"""
from __future__ import annotations
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from fastforge_core.auth import (
    JwtService, get_current_user, get_current_user_id,
)
from .service import IdentityService
from .schemas import (
    LoginRequest, RegisterRequest, TokenResponse, RefreshRequest,
    UserResponse, UserUpdate, ChangePasswordRequest, UserListResponse,
    RoleCreate, RoleUpdate, RoleResponse,
)


def create_identity_router(
    jwt_service: JwtService,
    get_db=None,
    prefix: str = "",
) -> APIRouter:
    """
    Factory that creates the identity router with the given JWT service.

    Usage:
        from fastforge_core.modules.identity import create_identity_router
        router = create_identity_router(jwt_service)
        app.include_router(router, prefix="/api/v1/auth", tags=["Auth"])
    """

    router = APIRouter()

    def _get_service(db: Session = Depends(get_db)) -> IdentityService:
        return IdentityService(db, jwt_service)

    # ── Auth Endpoints ───────────────────────────────────────────────────

    @router.post("/register", response_model=TokenResponse, status_code=201, tags=["Auth"])
    def register(data: RegisterRequest, service: IdentityService = Depends(_get_service)):
        """Register a new user account."""
        return service.register(data)

    @router.post("/login", response_model=TokenResponse, tags=["Auth"])
    def login(data: LoginRequest, service: IdentityService = Depends(_get_service)):
        """Login with email and password."""
        return service.login(data)

    @router.post("/refresh", response_model=TokenResponse, tags=["Auth"])
    def refresh(data: RefreshRequest, service: IdentityService = Depends(_get_service)):
        """Exchange refresh token for new token pair."""
        return service.refresh_token(data.refresh_token)

    @router.get("/me", response_model=UserResponse, tags=["Auth"])
    def get_me(
        user_id: str = Depends(get_current_user_id),
        service: IdentityService = Depends(_get_service),
    ):
        """Get current user's profile."""
        return service.get_current_profile(user_id)

    @router.post("/change-password", tags=["Auth"])
    def change_password(
        data: ChangePasswordRequest,
        user_id: str = Depends(get_current_user_id),
        service: IdentityService = Depends(_get_service),
    ):
        """Change current user's password."""
        return service.change_password(user_id, data)

    # ── User Management ──────────────────────────────────────────────────

    @router.get("/users", response_model=UserListResponse, tags=["User Management"])
    def list_users(
        page: int = Query(1, ge=1),
        page_size: int = Query(20, ge=1, le=100),
        search: Optional[str] = Query(None),
        service: IdentityService = Depends(_get_service),
    ):
        """List all users (admin)."""
        return service.list_users(page, page_size, search)

    @router.put("/users/{user_id}", response_model=UserResponse, tags=["User Management"])
    def update_user(
        user_id: int,
        data: UserUpdate,
        service: IdentityService = Depends(_get_service),
    ):
        """Update a user (admin)."""
        return service.update_user(user_id, data)

    @router.post("/users/{user_id}/roles", response_model=UserResponse, tags=["User Management"])
    def assign_roles(
        user_id: int,
        role_names: list[str],
        service: IdentityService = Depends(_get_service),
    ):
        """Assign roles to a user (admin)."""
        return service.assign_roles(user_id, role_names)

    # ── Role Management ──────────────────────────────────────────────────

    @router.get("/roles", response_model=list[RoleResponse], tags=["Role Management"])
    def list_roles(service: IdentityService = Depends(_get_service)):
        """List all roles."""
        return service.list_roles()

    @router.post("/roles", response_model=RoleResponse, status_code=201, tags=["Role Management"])
    def create_role(data: RoleCreate, service: IdentityService = Depends(_get_service)):
        """Create a new role with permissions."""
        return service.create_role(data)

    @router.put("/roles/{role_id}", response_model=RoleResponse, tags=["Role Management"])
    def update_role(
        role_id: int,
        data: RoleUpdate,
        service: IdentityService = Depends(_get_service),
    ):
        """Update a role and its permissions."""
        return service.update_role(role_id, data)

    @router.delete("/roles/{role_id}", tags=["Role Management"])
    def delete_role(role_id: int, service: IdentityService = Depends(_get_service)):
        """Delete a role."""
        return service.delete_role(role_id)

    return router
