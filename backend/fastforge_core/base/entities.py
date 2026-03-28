"""
FastForge Base Entities
=========================
entity base classes. Your models extend these to get
automatic audit fields, soft delete, etc.

Usage:
    from fastforge_core.base.entities import AuditedEntity, FullAuditedEntity

    class Product(FullAuditedEntity):
        __tablename__ = "products"
        name = Column(String(255), nullable=False)
        price = Column(Numeric(10, 2), nullable=False)
"""
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, Boolean, event
from sqlalchemy.orm import DeclarativeBase, declared_attr


class Base(DeclarativeBase):
    """SQLAlchemy declarative base for all FastForge entities."""
    pass


class Entity(Base):
    """
    Base entity with auto-incrementing integer PK.
    
    """
    __abstract__ = True

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    def __repr__(self):
        return f"<{self.__class__.__name__}(id={self.id})>"


class AuditedEntity(Entity):
    """
    Entity with creation/modification tracking.
    

    Auto-sets:
      - created_at: when record is first inserted
      - updated_at: when record is modified
      - created_by: user ID who created (if auth context available)
      - updated_by: user ID who last modified
    """
    __abstract__ = True

    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    created_by = Column(String(100), nullable=True)
    updated_by = Column(String(100), nullable=True)


class SoftDeleteEntity(AuditedEntity):
    """
    Audited entity with soft delete.
    Records are never physically deleted — is_deleted is set to True.
    

    The GenericRepository auto-filters soft-deleted records.
    """
    __abstract__ = True

    is_deleted = Column(Boolean, default=False, nullable=False, index=True)
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    deleted_by = Column(String(100), nullable=True)


class FullAuditedEntity(SoftDeleteEntity):
    """
    The most complete entity base — audit + soft delete.
    

    Use this as your default for business entities.
    """
    __abstract__ = True


# ─── Multi-Tenancy Mixin (opt-in) ───────────────────────────────────────────

class MultiTenantMixin:
    """
    Add this mixin to make an entity multi-tenant.
    

    Usage:
        class Product(FullAuditedEntity, MultiTenantMixin):
            __tablename__ = "products"
            ...

    The GenericRepository auto-filters by tenant_id.
    """
    @declared_attr
    def tenant_id(cls):
        return Column(String(50), nullable=True, index=True)
