"""
FastForge Identity Service
================================
Handles registration, login, token refresh, user CRUD, role management.

"""
from __future__ import annotations
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import select, func
from fastapi import HTTPException, status

from fastforge_core.auth import JwtService, hash_password, verify_password
from fastforge_core.middleware.exceptions import BusinessException
from .models import User, Role, user_roles, role_permissions
from .schemas import (
    LoginRequest, RegisterRequest, TokenResponse, UserResponse,
    UserUpdate, ChangePasswordRequest, UserListResponse,
    RoleCreate, RoleUpdate, RoleResponse,
)


class IdentityService:
    """
    Identity module service.
    Instantiate with a DB session and JWT service.
    """

    def __init__(self, db: Session, jwt_service: JwtService, tenant_id: Optional[str] = None):
        self.db = db
        self.jwt = jwt_service
        self.tenant_id = tenant_id

    # ─── Auth ────────────────────────────────────────────────────────────

    def register(self, data: RegisterRequest) -> TokenResponse:
        """Register a new user and return tokens."""
        # Check duplicates
        if self.db.query(User).filter(User.email == data.email).first():
            raise BusinessException("Email already registered", code="DuplicateEmail")
        if self.db.query(User).filter(User.username == data.username).first():
            raise BusinessException("Username already taken", code="DuplicateUsername")

        user = User(
            email=data.email,
            username=data.username,
            password_hash=hash_password(data.password),
            full_name=data.full_name,
            tenant_id=self.tenant_id,
        )

        # Assign default roles
        default_roles = self.db.query(Role).filter(Role.is_default == True).all()
        user.roles = default_roles

        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)

        return self._create_token_response(user)

    def login(self, data: LoginRequest) -> TokenResponse:
        """Authenticate and return tokens."""
        user = self.db.query(User).filter(User.email == data.email).first()
        if not user or not verify_password(data.password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password",
            )
        if not user.is_active:
            raise BusinessException("Account is deactivated", code="AccountInactive")
        if user.is_deleted:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Account not found")

        return self._create_token_response(user)

    def refresh_token(self, refresh_token: str) -> TokenResponse:
        """Exchange a refresh token for new token pair."""
        user_id = self.jwt.decode_refresh_token(refresh_token)
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired refresh token",
            )

        user = self.db.query(User).filter(User.id == int(user_id)).first()
        if not user or not user.is_active:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")

        return self._create_token_response(user)

    def get_current_profile(self, user_id: str) -> UserResponse:
        """Get current user's profile."""
        user = self.db.query(User).filter(User.id == int(user_id)).first()
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
        return self._to_user_response(user)

    def change_password(self, user_id: str, data: ChangePasswordRequest) -> dict:
        """Change current user's password."""
        user = self.db.query(User).filter(User.id == int(user_id)).first()
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

        if not verify_password(data.current_password, user.password_hash):
            raise BusinessException("Current password is incorrect", code="InvalidPassword")

        user.password_hash = hash_password(data.new_password)
        self.db.commit()
        return {"message": "Password changed successfully"}

    # ─── User Management ─────────────────────────────────────────────────

    def list_users(self, page: int = 1, page_size: int = 20, search: Optional[str] = None) -> UserListResponse:
        query = self.db.query(User).filter(User.is_deleted == False)
        if self.tenant_id:
            query = query.filter(User.tenant_id == self.tenant_id)
        if search:
            query = query.filter(
                (User.email.ilike(f"%{search}%")) |
                (User.username.ilike(f"%{search}%")) |
                (User.full_name.ilike(f"%{search}%"))
            )

        total = query.count()
        users = query.order_by(User.id.desc()).offset((page - 1) * page_size).limit(page_size).all()

        return UserListResponse(
            items=[self._to_user_response(u) for u in users],
            total=total,
            page=page,
            page_size=page_size,
        )

    def update_user(self, user_id: int, data: UserUpdate) -> UserResponse:
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

        update_data = data.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(user, field, value)
        self.db.commit()
        self.db.refresh(user)
        return self._to_user_response(user)

    def assign_roles(self, user_id: int, role_names: list[str]) -> UserResponse:
        """Assign roles to a user."""
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

        roles = self.db.query(Role).filter(Role.name.in_(role_names)).all()
        user.roles = roles
        self.db.commit()
        self.db.refresh(user)
        return self._to_user_response(user)

    # ─── Role Management ─────────────────────────────────────────────────

    def list_roles(self) -> list[RoleResponse]:
        roles = self.db.query(Role).filter(Role.is_deleted == False).all()
        return [self._to_role_response(r) for r in roles]

    def create_role(self, data: RoleCreate) -> RoleResponse:
        if self.db.query(Role).filter(Role.name == data.name).first():
            raise BusinessException(f"Role '{data.name}' already exists", code="DuplicateRole")

        role = Role(
            name=data.name,
            display_name=data.display_name,
            tenant_id=self.tenant_id,
        )
        self.db.add(role)
        self.db.commit()
        self.db.refresh(role)

        # Set permissions
        if data.permissions:
            self._set_role_permissions(role.id, data.permissions)

        return self._to_role_response(role)

    def update_role(self, role_id: int, data: RoleUpdate) -> RoleResponse:
        role = self.db.query(Role).filter(Role.id == role_id).first()
        if not role:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
        if role.is_static:
            raise BusinessException("Cannot modify static role", code="StaticRole")

        if data.display_name is not None:
            role.display_name = data.display_name
        if data.permissions is not None:
            self._set_role_permissions(role.id, data.permissions)

        self.db.commit()
        self.db.refresh(role)
        return self._to_role_response(role)

    def delete_role(self, role_id: int) -> dict:
        role = self.db.query(Role).filter(Role.id == role_id).first()
        if not role:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)
        if role.is_static:
            raise BusinessException("Cannot delete static role", code="StaticRole")

        role.is_deleted = True
        self.db.commit()
        return {"message": f"Role '{role.name}' deleted"}

    # ─── Helpers ─────────────────────────────────────────────────────────

    def _create_token_response(self, user: User) -> TokenResponse:
        permissions = self._get_user_permissions(user)
        role_names = [r.name for r in user.roles]

        tokens = self.jwt.create_token_pair(
            user_id=str(user.id),
            email=user.email,
            roles=role_names,
            permissions=list(permissions),
            tenant_id=user.tenant_id,
        )

        return TokenResponse(
            access_token=tokens["access_token"],
            refresh_token=tokens["refresh_token"],
            token_type=tokens["token_type"],
            expires_in=tokens["expires_in"],
            user=self._to_user_response(user, permissions),
        )

    def _to_user_response(self, user: User, permissions: set[str] = None) -> UserResponse:
        if permissions is None:
            permissions = self._get_user_permissions(user)
        return UserResponse(
            id=user.id,
            email=user.email,
            username=user.username,
            full_name=user.full_name,
            is_active=user.is_active,
            roles=[r.name for r in user.roles],
            permissions=list(permissions),
            created_at=user.created_at,
        )

    def _to_role_response(self, role: Role) -> RoleResponse:
        perms = self._get_role_permissions(role.id)
        return RoleResponse(
            id=role.id,
            name=role.name,
            display_name=role.display_name,
            is_default=role.is_default,
            permissions=perms,
        )

    def _get_user_permissions(self, user: User) -> set[str]:
        """Collect all permissions across all user roles."""
        perms = set()
        for role in user.roles:
            perms.update(self._get_role_permissions(role.id))
        return perms

    def _get_role_permissions(self, role_id: int) -> list[str]:
        """Get permissions for a role from the join table."""
        rows = self.db.execute(
            select(role_permissions.c.permission).where(role_permissions.c.role_id == role_id)
        ).fetchall()
        return [r[0] for r in rows]

    def _set_role_permissions(self, role_id: int, permissions: list[str]):
        """Replace all permissions for a role."""
        self.db.execute(role_permissions.delete().where(role_permissions.c.role_id == role_id))
        for perm in permissions:
            self.db.execute(role_permissions.insert().values(role_id=role_id, permission=perm))
        self.db.commit()
