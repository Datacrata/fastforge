"""
FastForge Data Seeding
=========================
data seeding system.
Define seeders that run on app startup to populate initial data.

Usage:
    from fastforge_core.modules.data_seeding import DataSeeder, seed_manager

    class RoleSeeder(DataSeeder):
        order = 1  # Run order (lower = first)

        def seed(self, db: Session):
            if not db.query(Role).filter(Role.name == "admin").first():
                db.add(Role(name="admin", display_name="Administrator", is_static=True, is_default=False))
                db.add(Role(name="user", display_name="User", is_static=True, is_default=True))
                db.commit()

    # Register
    seed_manager.register(RoleSeeder)

    # Run all seeders (call in main.py after table creation)
    seed_manager.run_all(db)
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Type
from sqlalchemy.orm import Session
import logging

logger = logging.getLogger("fastforge.seeding")


class DataSeeder(ABC):
    """
    Base class for data seeders.
    Override seed() with your initialization logic.
    """
    order: int = 100  # Execution order (lower runs first)

    @abstractmethod
    def seed(self, db: Session):
        """Insert initial data. Should be idempotent (safe to run multiple times)."""
        pass


class DataSeedManager:
    """Manages and executes data seeders in order."""

    def __init__(self):
        self._seeders: list[Type[DataSeeder]] = []

    def register(self, seeder_class: Type[DataSeeder]):
        """Register a seeder class."""
        self._seeders.append(seeder_class)
        return seeder_class

    def run_all(self, db: Session):
        """Run all registered seeders in order."""
        sorted_seeders = sorted(self._seeders, key=lambda s: s.order)
        for seeder_class in sorted_seeders:
            name = seeder_class.__name__
            try:
                logger.info(f"Running seeder: {name}")
                seeder = seeder_class()
                seeder.seed(db)
                logger.info(f"Seeder completed: {name}")
            except Exception as e:
                logger.error(f"Seeder failed: {name} — {e}")
                raise


# Global instance
seed_manager = DataSeedManager()


# ─── Built-in Seeders ───────────────────────────────────────────────────────

class DefaultRoleSeeder(DataSeeder):
    """Creates default admin and user roles."""
    order = 1

    def seed(self, db: Session):
        from fastforge_core.modules.identity.models import Role

        for role_data in [
            {"name": "admin", "display_name": "Administrator", "is_static": True, "is_default": False},
            {"name": "user", "display_name": "User", "is_static": True, "is_default": True},
        ]:
            existing = db.query(Role).filter(Role.name == role_data["name"]).first()
            if not existing:
                db.add(Role(**role_data))
                logger.info(f"  Created role: {role_data['name']}")
        db.commit()


class DefaultAdminSeeder(DataSeeder):
    """Creates a default admin user if none exists."""
    order = 2

    def seed(self, db: Session):
        from fastforge_core.modules.identity.models import User, Role
        from fastforge_core.auth.password import hash_password

        admin_email = "admin@fastforge.dev"
        if db.query(User).filter(User.email == admin_email).first():
            return

        admin_role = db.query(Role).filter(Role.name == "admin").first()
        user = User(
            email=admin_email,
            username="admin",
            password_hash=hash_password("admin123"),
            full_name="System Administrator",
            is_active=True,
            is_email_confirmed=True,
        )
        if admin_role:
            user.roles = [admin_role]
        db.add(user)
        db.commit()
        logger.info(f"  Created admin user: {admin_email} (password: admin123)")


# Register built-in seeders
seed_manager.register(DefaultRoleSeeder)
seed_manager.register(DefaultAdminSeeder)
