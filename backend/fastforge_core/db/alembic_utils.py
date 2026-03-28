"""
FastForge Alembic Integration
===================================
Auto-generates Alembic migration files when you run `fastforge crud`.

Also provides `fastforge migrate` commands:
  fastforge migrate init      — Initialize Alembic in your project
  fastforge migrate generate  — Auto-detect model changes and create migration
  fastforge migrate up        — Apply pending migrations
  fastforge migrate down      — Rollback last migration
"""
from __future__ import annotations
import os
import subprocess
from pathlib import Path


def init_alembic(backend_path: str) -> bool:
    """
    Initialize Alembic in the backend project.
    Creates alembic.ini and migrations/ directory.
    """
    alembic_ini = Path(backend_path) / "alembic.ini"
    migrations_dir = Path(backend_path) / "migrations"

    if alembic_ini.exists():
        print("  ⏭ Alembic already initialized")
        return True

    try:
        result = subprocess.run(
            ["alembic", "init", "migrations"],
            cwd=backend_path,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            _patch_alembic_env(backend_path)
            print("  ✅ Alembic initialized")
            return True
        else:
            print(f"  ⚠ Alembic init failed: {result.stderr}")
            return False
    except FileNotFoundError:
        print("  ⚠ Alembic not installed. Run: pip install alembic")
        return False


def generate_migration(backend_path: str, message: str) -> bool:
    """
    Auto-generate a migration by comparing models to database.
    Equivalent to: alembic revision --autogenerate -m "message"
    """
    try:
        result = subprocess.run(
            ["alembic", "revision", "--autogenerate", "-m", message],
            cwd=backend_path,
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            # Extract the migration file path from output
            for line in result.stdout.split("\n"):
                if "Generating" in line:
                    print(f"  ✅ Migration: {line.strip()}")
                    return True
            print(f"  ✅ Migration generated")
            return True
        else:
            print(f"  ⚠ Migration generation failed: {result.stderr}")
            return False
    except FileNotFoundError:
        print("  ⚠ Alembic not installed")
        return False


def run_migrations(backend_path: str, direction: str = "up") -> bool:
    """Run migrations up or down."""
    cmd = ["alembic", "upgrade", "head"] if direction == "up" else ["alembic", "downgrade", "-1"]
    try:
        result = subprocess.run(cmd, cwd=backend_path, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"  ✅ Migration {'applied' if direction == 'up' else 'reverted'}")
            return True
        else:
            print(f"  ⚠ Migration failed: {result.stderr}")
            return False
    except FileNotFoundError:
        print("  ⚠ Alembic not installed")
        return False


def _patch_alembic_env(backend_path: str):
    """
    Patch the generated alembic/env.py to use our models and config.
    """
    env_path = Path(backend_path) / "migrations" / "env.py"
    if not env_path.exists():
        return

    patch = '''
# ── FastForge Auto-Config ──────────────────────────────────────────────────
# Import all your models here so Alembic can detect them
from app.core.config import settings
from fastforge_core.base.entities import Base

# Import identity module models
try:
    from fastforge_core.modules.identity.models import User, Role
except ImportError:
    pass

# Import your app models
# (fastforge crud will add imports here)
# FASTFORGE_MODEL_IMPORTS

config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)
target_metadata = Base.metadata
# ── End FastForge Auto-Config ──────────────────────────────────────────────
'''

    content = env_path.read_text()
    # Insert after the initial imports
    if "FastForge Auto-Config" not in content:
        content = content.replace(
            "target_metadata = None",
            patch,
        )
        env_path.write_text(content)
