"""
FastForge Permissions
========================
permission system for FastAPI.

Usage:
    @router.post("/products")
    @require_permission("Products.Create")
    def create_product(data: ProductCreate, user = Depends(get_current_user)):
        ...

    @router.delete("/products/{id}")
    @require_permissions("Products.Delete", "Products.Admin", require_all=False)
    def delete_product(id: int):
        ...
"""
from __future__ import annotations
from functools import wraps
from typing import Optional, Callable
from fastapi import HTTPException, status, Depends, Request


def require_permission(permission: str):
    """
    Decorator that checks a single permission.
    Name")].

    The user's permissions are expected in request.state.permissions (Set[str])
    or from the JWT token claims.
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, request: Request = None, **kwargs):
            _check_permission(request, permission)
            return await func(*args, **kwargs) if _is_async(func) else func(*args, **kwargs)
        # Preserve FastAPI's ability to inspect the signature
        wrapper.__signature__ = _preserve_signature(func)
        return wrapper
    return decorator


def require_permissions(*permissions: str, require_all: bool = True):
    """
    Decorator that checks multiple permissions.

    Args:
        permissions: Permission names to check
        require_all: If True, ALL permissions required. If False, ANY is sufficient.
    """
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, request: Request = None, **kwargs):
            user_perms = _get_user_permissions(request)
            if require_all:
                missing = [p for p in permissions if p not in user_perms]
                if missing:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"Missing permissions: {', '.join(missing)}",
                    )
            else:
                if not any(p in user_perms for p in permissions):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"Requires at least one of: {', '.join(permissions)}",
                    )
            return await func(*args, **kwargs) if _is_async(func) else func(*args, **kwargs)
        wrapper.__signature__ = _preserve_signature(func)
        return wrapper
    return decorator


def require_role(role: str):
    """Check that the current user has a specific role."""
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, request: Request = None, **kwargs):
            user_roles = _get_user_roles(request)
            if role not in user_roles:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Requires role: {role}",
                )
            return await func(*args, **kwargs) if _is_async(func) else func(*args, **kwargs)
        wrapper.__signature__ = _preserve_signature(func)
        return wrapper
    return decorator


# ─── Permission Definition ───────────────────────────────────────────────────

class PermissionGroup:
    """
    Define permissions for an entity. 

    Usage:
        ProductPermissions = PermissionGroup("Products", [
            "Create", "Read", "Update", "Delete", "Export"
        ])

        # Then use:
        @require_permission(ProductPermissions.Create)
        def create_product(...):

        # Gives you: "Products.Create", "Products.Read", etc.
    """

    def __init__(self, group_name: str, permissions: list[str]):
        self.group_name = group_name
        self._permissions = {}
        for perm in permissions:
            full_name = f"{group_name}.{perm}"
            self._permissions[perm] = full_name
            setattr(self, perm, full_name)

    def all(self) -> list[str]:
        """Get all permission names in this group."""
        return list(self._permissions.values())

    def __repr__(self):
        return f"PermissionGroup({self.group_name}, {list(self._permissions.keys())})"


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _check_permission(request: Optional[Request], permission: str):
    user_perms = _get_user_permissions(request)
    if permission not in user_perms:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Permission denied: {permission}",
        )


def _get_user_permissions(request: Optional[Request]) -> set[str]:
    """Extract permissions from request state (set by auth middleware)."""
    if request and hasattr(request.state, "permissions"):
        return set(request.state.permissions)
    return set()


def _get_user_roles(request: Optional[Request]) -> set[str]:
    """Extract roles from request state."""
    if request and hasattr(request.state, "roles"):
        return set(request.state.roles)
    return set()


def _is_async(func):
    import asyncio
    return asyncio.iscoroutinefunction(func)


def _preserve_signature(func):
    import inspect
    return inspect.signature(func)
