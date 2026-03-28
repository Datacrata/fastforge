"""
FastForge Core — Runtime Framework for FastAPI
=================================================
Full-stack base classes, repositories, services, auth, permissions, and modules.

Quick reference:
    from fastforge_core import FullAuditedEntity, GenericRepository, CrudAppService
    from fastforge_core import require_permission, PermissionGroup
    from fastforge_core import BusinessException, register_exception_handlers
    from fastforge_core.auth import JwtService, TokenConfig, AuthMiddleware, get_current_user
    from fastforge_core.modules.identity import create_identity_router
    from fastforge_core.settings import AppSettings
    from fastforge_core.background import BackgroundJob, job_manager
"""
# Base
from .base.entities import Entity, AuditedEntity, SoftDeleteEntity, FullAuditedEntity, MultiTenantMixin, Base
from .base.repository import GenericRepository, PagedResult
from .base.app_service import CrudAppService
from .base.permissions import require_permission, require_permissions, require_role, PermissionGroup

# Middleware
from .middleware.exceptions import (
    BusinessException, EntityNotFoundException,
    UnauthorizedException, ForbiddenException,
    register_exception_handlers,
)

# DB
from .db.session import DatabaseConfig

__all__ = [
    # Base
    "Base", "Entity", "AuditedEntity", "SoftDeleteEntity", "FullAuditedEntity", "MultiTenantMixin",
    "GenericRepository", "PagedResult",
    "CrudAppService",
    "require_permission", "require_permissions", "require_role", "PermissionGroup",
    # Middleware
    "BusinessException", "EntityNotFoundException", "UnauthorizedException", "ForbiddenException",
    "register_exception_handlers",
    # DB
    "DatabaseConfig",
]
