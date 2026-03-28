"""
FastForge Settings System
==============================
application settings.
Key-value store with scoping: global → tenant → user.

Usage:
    settings = AppSettings(db)
    
    # Set/get global settings
    settings.set("App.Theme", "dark")
    theme = settings.get("App.Theme", default="light")
    
    # Tenant-scoped settings
    settings.set("Billing.Plan", "pro", tenant_id="tenant-1")
    plan = settings.get("Billing.Plan", tenant_id="tenant-1")
    
    # User-scoped settings
    settings.set("UI.Language", "es", user_id="user-42")
"""
from __future__ import annotations
from typing import Optional
from sqlalchemy import Column, String, Text, Integer
from sqlalchemy.orm import Session

from fastforge_core.base.entities import Base


class SettingValue(Base):
    """Stores a single setting value."""
    __tablename__ = "fastforge_settings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), nullable=False, index=True)
    value = Column(Text, nullable=True)
    provider_name = Column(String(50), nullable=False, default="G")  # G=Global, T=Tenant, U=User
    provider_key = Column(String(100), nullable=True)  # tenant_id or user_id


class AppSettings:
    """
    Settings manager with hierarchical resolution:
    User setting > Tenant setting > Global setting > Default
    """

    def __init__(self, db: Session):
        self.db = db

    def get(
        self,
        name: str,
        default: Optional[str] = None,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> Optional[str]:
        """
        Get a setting value with hierarchical resolution.
        Checks: user → tenant → global → default
        """
        # Check user-level
        if user_id:
            val = self._get_raw(name, "U", user_id)
            if val is not None:
                return val

        # Check tenant-level
        if tenant_id:
            val = self._get_raw(name, "T", tenant_id)
            if val is not None:
                return val

        # Check global
        val = self._get_raw(name, "G", None)
        if val is not None:
            return val

        return default

    def set(
        self,
        name: str,
        value: str,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ):
        """Set a setting value at the appropriate scope."""
        if user_id:
            self._set_raw(name, value, "U", user_id)
        elif tenant_id:
            self._set_raw(name, value, "T", tenant_id)
        else:
            self._set_raw(name, value, "G", None)

    def delete(
        self,
        name: str,
        tenant_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ):
        """Delete a setting."""
        provider_name = "G"
        provider_key = None
        if user_id:
            provider_name, provider_key = "U", user_id
        elif tenant_id:
            provider_name, provider_key = "T", tenant_id

        query = self.db.query(SettingValue).filter(
            SettingValue.name == name,
            SettingValue.provider_name == provider_name,
        )
        if provider_key:
            query = query.filter(SettingValue.provider_key == provider_key)
        else:
            query = query.filter(SettingValue.provider_key.is_(None))
        query.delete()
        self.db.commit()

    def get_all(self, prefix: Optional[str] = None, tenant_id: Optional[str] = None) -> dict[str, str]:
        """Get all settings matching a prefix."""
        query = self.db.query(SettingValue)
        if prefix:
            query = query.filter(SettingValue.name.like(f"{prefix}%"))

        # Collect with hierarchy: global first, then tenant overrides
        result = {}
        for row in query.filter(SettingValue.provider_name == "G").all():
            result[row.name] = row.value
        if tenant_id:
            for row in query.filter(SettingValue.provider_name == "T", SettingValue.provider_key == tenant_id).all():
                result[row.name] = row.value
        return result

    # ─── Internal ────────────────────────────────────────────────────────

    def _get_raw(self, name: str, provider_name: str, provider_key: Optional[str]) -> Optional[str]:
        query = self.db.query(SettingValue).filter(
            SettingValue.name == name,
            SettingValue.provider_name == provider_name,
        )
        if provider_key:
            query = query.filter(SettingValue.provider_key == provider_key)
        else:
            query = query.filter(SettingValue.provider_key.is_(None))
        row = query.first()
        return row.value if row else None

    def _set_raw(self, name: str, value: str, provider_name: str, provider_key: Optional[str]):
        query = self.db.query(SettingValue).filter(
            SettingValue.name == name,
            SettingValue.provider_name == provider_name,
        )
        if provider_key:
            query = query.filter(SettingValue.provider_key == provider_key)
        else:
            query = query.filter(SettingValue.provider_key.is_(None))

        existing = query.first()
        if existing:
            existing.value = value
        else:
            self.db.add(SettingValue(
                name=name, value=value,
                provider_name=provider_name, provider_key=provider_key,
            ))
        self.db.commit()
