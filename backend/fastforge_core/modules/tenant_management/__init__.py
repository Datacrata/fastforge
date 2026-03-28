"""
FastForge Tenant Management Module
=======================================
Mount in your app:
    from fastforge_core.modules.tenant_management import create_tenant_router
    app.include_router(create_tenant_router(get_db), prefix="/api/v1/tenants")
"""
from .service import create_tenant_router, TenantService
from .models import Tenant, TenantFeature
from .schemas import TenantCreate, TenantUpdate, TenantResponse, TenantListResponse

__all__ = [
    "create_tenant_router", "TenantService",
    "Tenant", "TenantFeature",
    "TenantCreate", "TenantUpdate", "TenantResponse", "TenantListResponse",
]
