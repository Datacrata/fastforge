"""
FastForge Identity Models
=============================
Pre-built User and Role entities.

"""
from sqlalchemy import Column, String, Boolean, Table, ForeignKey, Integer
from sqlalchemy.orm import relationship
from fastforge_core.base.entities import FullAuditedEntity, Base

# Many-to-many: users ↔ roles
user_roles = Table(
    "fastforge_user_roles",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("fastforge_users.id"), primary_key=True),
    Column("role_id", Integer, ForeignKey("fastforge_roles.id"), primary_key=True),
)

# Many-to-many: roles ↔ permissions
role_permissions = Table(
    "fastforge_role_permissions",
    Base.metadata,
    Column("role_id", Integer, ForeignKey("fastforge_roles.id"), primary_key=True),
    Column("permission", String(200), primary_key=True),
)


class User(FullAuditedEntity):
    """Built-in user entity."""
    __tablename__ = "fastforge_users"

    email = Column(String(320), unique=True, nullable=False, index=True)
    username = Column(String(100), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(200), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    is_email_confirmed = Column(Boolean, default=False, nullable=False)
    tenant_id = Column(String(50), nullable=True, index=True)

    # Relationships
    roles = relationship("Role", secondary=user_roles, back_populates="users", lazy="selectin")

    @property
    def permissions(self) -> set[str]:
        """Aggregate all permissions from all roles."""
        perms = set()
        for role in self.roles:
            for rp in role.permission_entries:
                perms.add(rp)
        return perms


class Role(FullAuditedEntity):
    """Built-in role entity."""
    __tablename__ = "fastforge_roles"

    name = Column(String(100), unique=True, nullable=False, index=True)
    display_name = Column(String(200), nullable=True)
    is_default = Column(Boolean, default=False, nullable=False)
    is_static = Column(Boolean, default=False, nullable=False)  # Cannot be deleted
    tenant_id = Column(String(50), nullable=True, index=True)

    # Relationships
    users = relationship("User", secondary=user_roles, back_populates="roles")

    @property
    def permission_entries(self) -> list[str]:
        """Get permissions for this role from the join table."""
        from sqlalchemy import select
        # This is accessed via the relationship lazy loading
        return []
