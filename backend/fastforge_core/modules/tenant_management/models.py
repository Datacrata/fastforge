"""
FastForge Tenant Management Models
=======================================

Stores tenant metadata and connection strings.
"""
from sqlalchemy import Column, String, Boolean, Text, Integer
from fastforge_core.base.entities import AuditedEntity


class Tenant(AuditedEntity):
    """Represents a tenant in a multi-tenant SaaS application."""
    __tablename__ = "fastforge_tenants"

    name = Column(String(100), unique=True, nullable=False, index=True)
    display_name = Column(String(200), nullable=True)
    connection_string = Column(Text, nullable=True)  # For separate-DB tenants
    is_active = Column(Boolean, default=True, nullable=False)
    edition = Column(String(50), nullable=True)  # "free", "pro", "enterprise"
    admin_email = Column(String(320), nullable=True)


class TenantFeature(AuditedEntity):
    """Per-tenant feature flags. FastForge's feature system."""
    __tablename__ = "fastforge_tenant_features"

    tenant_id = Column(Integer, nullable=False, index=True)
    feature_name = Column(String(200), nullable=False)
    value = Column(String(500), nullable=True)  # "true"/"false" or a limit like "100"
