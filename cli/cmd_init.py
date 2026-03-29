"""
fastforge init — Project Scaffolding
========================================
Creates FastAPI backend by default. Use --react to include React frontend,
or run `fastforge add-frontend` later.
"""
from __future__ import annotations
import os
import subprocess
import shutil
from pathlib import Path
from datetime import datetime
import json


def run_init(project_name: str, db: str = "postgres", with_react: bool = False):
    """Scaffold a new FastForge project. Backend only by default."""
    print(f"\n⚡ FastForge — Initializing project: {project_name}\n")

    root = Path(project_name)
    be = root / "backend"

    _check_prerequisites(require_node=with_react)

    # ══════════════════════════════════════════════════════════════════════
    #  BACKEND
    # ══════════════════════════════════════════════════════════════════════
    print("📦 Backend...")

    # Create app directories
    for d in ["app/models", "app/schemas", "app/repositories", "app/services",
              "app/permissions", "app/api/routes", "app/core"]:
        _write(be / d / "__init__.py", "")

    # ── Config ────────────────────────────────────────────────────────────
    db_url = {
        "postgres": "postgresql://localhost/fastforge_db",
        "sqlite": "sqlite:///./app.db",
        "mysql": "mysql+pymysql://root:password@localhost/fastforge_db",
        "mongodb": "mongodb://localhost:27017/fastforge_db",
    }.get(db, "postgresql://localhost/fastforge_db")

    _write(be / "app" / "core" / "__init__.py", "")
    _write(be / "app" / "core" / "config.py", f'''"""Application configuration."""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "{project_name}"
    DEBUG: bool = True
    DATABASE_URL: str = "{db_url}"
    API_PREFIX: str = "/api/v1"
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:3000"]
    JWT_SECRET: str = "change-this-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60

    class Config:
        env_file = ".env"


settings = Settings()
''')

    if db == "mongodb":
        _write(be / "app" / "db.py", '''"""MongoDB connection."""
from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie
from app.core.config import settings

client = AsyncIOMotorClient(settings.DATABASE_URL)
database = client.get_default_database()


async def init_db(document_models: list):
    """Initialize Beanie with document models."""
    await init_beanie(database=database, document_models=document_models)
''')
    else:
        _write(be / "app" / "db.py", '''"""Database session."""
from fastforge_core import DatabaseConfig
from fastforge_core.base.entities import Base
from app.core.config import settings

db_config = DatabaseConfig(url=settings.DATABASE_URL, echo=settings.DEBUG)
get_db = db_config.get_db
''')

    _write(be / "app" / "api" / "router.py", '''"""Main API Router — auto-registers entity routes."""
from fastapi import APIRouter

api_router = APIRouter()

# FASTFORGE_ROUTER_IMPORTS
# FASTFORGE_ROUTER_INCLUDES
''')

    _write(be / "app" / "main.py", f'''"""
{project_name} — FastAPI Application
Built with FastForge Framework
"""
from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect

from app.core.config import settings
from app.db import db_config, get_db, Base
from app.api.router import api_router
from fastforge_core import register_exception_handlers
from fastforge_core.middleware.audit import AuditLogMiddleware
from fastforge_core.auth import JwtService, TokenConfig, AuthMiddleware
from fastforge_core.modules.identity import create_identity_router
from fastforge_core.modules.identity.models import User, Role  # noqa
from fastforge_core.modules.tenant_management import create_tenant_router
from fastforge_core.modules.tenant_management.models import Tenant, TenantFeature  # noqa
from fastforge_core.modules.data_seeding import seed_manager
from fastforge_core.settings import SettingValue  # noqa

# FASTFORGE_MODEL_IMPORTS

logger = logging.getLogger("fastforge")

jwt_service = JwtService(TokenConfig(
    secret=settings.JWT_SECRET,
    algorithm=settings.JWT_ALGORITHM,
    access_expire_minutes=settings.JWT_EXPIRE_MINUTES,
))


def _needs_init() -> bool:
    """Check if tables need to be created (first run or empty DB)."""
    inspector = inspect(db_config.engine)
    return "fastforge_users" not in inspector.get_table_names()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ──────────────────────────────────────────────────────
    if _needs_init():
        logger.info("First run detected — creating tables and seeding data...")
        Base.metadata.create_all(bind=db_config.engine)

        # Stamp Alembic so it knows the DB is current
        import subprocess, pathlib
        backend_dir = str(pathlib.Path(__file__).resolve().parent.parent)
        subprocess.run(["alembic", "stamp", "head"], cwd=backend_dir,
                        capture_output=True)

        db = next(db_config.get_db())
        try:
            seed_manager.run_all(db)
        finally:
            db.close()
    else:
        logger.info("Database already initialized, skipping create_all & seeding.")
    yield
    # ── Shutdown ─────────────────────────────────────────────────────


app = FastAPI(
    title=settings.APP_NAME,
    docs_url=f"{{settings.API_PREFIX}}/docs",
    openapi_url=f"{{settings.API_PREFIX}}/openapi.json",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(AuthMiddleware, jwt_service=jwt_service)
app.add_middleware(AuditLogMiddleware)

register_exception_handlers(app, debug=settings.DEBUG)

app.include_router(
    create_identity_router(jwt_service, get_db=get_db),
    prefix=f"{{settings.API_PREFIX}}/auth",
)
app.include_router(
    create_tenant_router(get_db),
    prefix=f"{{settings.API_PREFIX}}/tenants",
)
app.include_router(api_router, prefix=settings.API_PREFIX)


@app.get("/health")
def health():
    return {{"status": "ok", "app": settings.APP_NAME}}
''')

    _write(be / ".env", f'''APP_NAME="{project_name}"
DEBUG=true
DATABASE_URL={db_url}
JWT_SECRET=change-this-in-production-{datetime.now().timestamp():.0f}
''')

    # ── pyproject.toml ───────────────────────────────────────────────────
    db_dep = {
        "postgres": '\n    "psycopg2-binary>=2.9.0",',
        "mysql": '\n    "pymysql>=1.1.0",',
        "mongodb": '\n    "motor>=3.3.0",\n    "beanie>=1.25.0",',
        "sqlite": "",
    }.get(db, "")

    # Find fastforge_core source for path dependency
    core_path = _find_fastforge_core()
    if core_path:
        # Path from the generated backend dir to fastforge_core's parent (the package root)
        core_source = f'\n\n[tool.uv.sources]\nfastforge-core = {{ path = "{core_path.parent}" }}'
    else:
        core_source = ""
        print("  ⚠ Could not find fastforge_core. Add it manually to pyproject.toml.")

    # MongoDB doesn't use SQLAlchemy/Alembic
    if db == "mongodb":
        deps = f'''    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.30.0",
    "pydantic>=2.0.0",
    "pydantic-settings>=2.0.0",
    "python-multipart>=0.0.9",
    "python-jose[cryptography]>=3.3.0",
    "bcrypt>=4.0.0",
    "fastforge-core",{db_dep}'''
    else:
        deps = f'''    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.30.0",
    "sqlalchemy>=2.0.0",
    "pydantic>=2.0.0",
    "pydantic-settings>=2.0.0",
    "python-multipart>=0.0.9",
    "alembic>=1.13.0",
    "python-jose[cryptography]>=3.3.0",
    "bcrypt>=4.0.0",
    "fastforge-core",{db_dep}'''

    _write(be / "pyproject.toml", f'''[project]
name = "{project_name}-backend"
version = "0.1.0"
description = "{project_name} backend — built with FastForge"
requires-python = ">=3.10"
dependencies = [
{deps}
]

[tool.uv]
dev-dependencies = [
    "pytest>=8.0.0",
    "httpx>=0.27.0",
]{core_source}
''')

    # ── Config ────────────────────────────────────────────────────────────
    # Paths are stored relative to the config file (which lives in root/)
    paths = {"backend": str(be.relative_to(root))}
    config = {
        "project": project_name,
        "version": "0.3.0",
        "created_at": datetime.now().isoformat(),
        "database": db,
        "paths": paths,
    }

    _write(root / ".gitignore", """__pycache__/
*.pyc
.venv/
.env
*.db
node_modules/
dist/
uv.lock
""")

    # ══════════════════════════════════════════════════════════════════════
    #  FRONTEND (optional)
    # ══════════════════════════════════════════════════════════════════════
    if with_react:
        fe = root / "frontend"
        _scaffold_frontend(fe, project_name)
        paths["frontend"] = str(fe.relative_to(root))

    _write(root / "fastforge.json", json.dumps(config, indent=2))

    # ══════════════════════════════════════════════════════════════════════
    #  INSTALL
    # ══════════════════════════════════════════════════════════════════════
    print(f"\n{'─' * 60}")
    print("📥 Installing dependencies...\n")

    _install_backend(be)
    if with_react:
        _install_frontend(fe)

    # ── Done ──────────────────────────────────────────────────────────────
    print(f"\n{'─' * 60}")
    print(f"✅ Project '{project_name}' ready!\n")
    print(f"  cd {project_name}\n")
    print(f"  # Create entity:")
    print(f"  fastforge crud product")
    print(f"  # Edit backend/app/models/product.py")
    print(f"  fastforge generate product\n")
    print(f"  # Start backend:")
    print(f"  cd backend && uv run uvicorn app.main:app --reload")
    print(f"  # → http://localhost:8000/api/v1/docs\n")
    if with_react:
        print(f"  # Start frontend:")
        print(f"  cd frontend && npm run dev")
        print(f"  # → http://localhost:5173\n")
    else:
        print(f"  # Add React frontend later:")
        print(f"  fastforge add-frontend\n")


def _scaffold_frontend(fe: Path, project_name: str):
    """Create React + Vite + TypeScript frontend."""
    print("\n📦 Frontend...")

    _write(fe / "src" / "api" / ".gitkeep", "# Generated by: fastforge generate-client\n")

    _write(fe / "package.json", json.dumps({
        "name": project_name,
        "private": True,
        "version": "0.1.0",
        "type": "module",
        "scripts": {
            "dev": "vite",
            "build": "tsc -b && vite build",
            "preview": "vite preview",
            "generate-api": f"fastforge generate-client --input http://localhost:8000/api/v1/openapi.json --output ./src/api"
        },
        "dependencies": {
            "react": "^18.3.0",
            "react-dom": "^18.3.0",
            "@tanstack/react-query": "^5.50.0",
            "axios": "^1.7.0",
            "react-router-dom": "^6.25.0",
        },
        "devDependencies": {
            "@types/react": "^18.3.0",
            "@types/react-dom": "^18.3.0",
            "typescript": "^5.5.0",
            "vite": "^5.4.0",
            "@vitejs/plugin-react": "^4.3.0",
        }
    }, indent=2))

    _write(fe / "tsconfig.json", json.dumps({
        "compilerOptions": {
            "target": "ES2020",
            "useDefineForClassFields": True,
            "lib": ["ES2020", "DOM", "DOM.Iterable"],
            "module": "ESNext",
            "skipLibCheck": True,
            "moduleResolution": "bundler",
            "allowImportingTsExtensions": True,
            "isolatedModules": True,
            "moduleDetection": "force",
            "noEmit": True,
            "jsx": "react-jsx",
            "strict": True,
            "noUnusedLocals": True,
            "noUnusedParameters": True,
            "noFallthroughCasesInSwitch": True,
            "paths": {"@/*": ["./src/*"]}
        },
        "include": ["src"]
    }, indent=2))

    _write(fe / "vite.config.ts", '''import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  resolve: { alias: { '@': '/src' } },
  server: {
    port: 5173,
    proxy: { '/api': { target: 'http://localhost:8000', changeOrigin: true } },
  },
})
''')

    _write(fe / "index.html", f'''<!DOCTYPE html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>{project_name}</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
''')

    _write(fe / "src" / "main.tsx", '''import React from 'react'
import ReactDOM from 'react-dom/client'
import App from './App'

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
)
''')

    _write(fe / "src" / "App.tsx", '''import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

const queryClient = new QueryClient()

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <div style={{ padding: '2rem', fontFamily: 'system-ui' }}>
        <h1>⚡ {0} is running</h1>
        <p>Backend: <a href="http://localhost:8000/api/v1/docs">Swagger Docs</a></p>
        <p>Run <code>fastforge generate-client</code> to generate your API client.</p>
      </div>
    </QueryClientProvider>
  )
}
'''.replace('{0}', project_name))

    _write(fe / ".env", "VITE_API_URL=http://localhost:8000/api/v1\n")


def add_frontend(config: dict, config_dir: Path):
    """Add React frontend to an existing FastForge project."""
    project_name = config.get("project", "my-app")
    fe = config_dir / "frontend"

    print(f"\n⚡ FastForge — Adding React frontend to '{project_name}'\n")

    _check_prerequisites(require_node=True, require_uv=False)
    _scaffold_frontend(fe, project_name)

    # Update config
    config["paths"]["frontend"] = str(fe.relative_to(config_dir))
    config_file = config_dir / "fastforge.json"
    config_file.write_text(json.dumps(config, indent=2))
    print(f"  ✅ Updated fastforge.json")

    _install_frontend(fe)

    print(f"\n{'─' * 60}")
    print(f"✅ Frontend added!\n")
    print(f"  cd frontend && npm run dev")
    print(f"  # → http://localhost:5173\n")


def _find_fastforge_core() -> Path | None:
    """Find the fastforge_core source directory."""
    # Option 1: Relative to this CLI file (fastforge-framework/backend/fastforge_core)
    cli_dir = Path(__file__).resolve().parent  # cli/
    framework_dir = cli_dir.parent             # fastforge-framework/
    candidate = framework_dir / "backend" / "fastforge_core"
    if candidate.exists() and (candidate / "__init__.py").exists():
        return candidate

    # Option 2: Installed as a package — find via importlib
    try:
        import fastforge_core
        pkg_path = Path(fastforge_core.__file__).parent
        if pkg_path.exists():
            return pkg_path
    except ImportError:
        pass

    # Option 3: Check common locations
    for check in [
        Path.home() / "fastforge-framework" / "backend" / "fastforge_core",
        Path("/usr/local/lib/python3.11/site-packages/fastforge_core"),
        Path("/usr/local/lib/python3.12/site-packages/fastforge_core"),
    ]:
        if check.exists():
            return check

    return None


# ─── Installation ────────────────────────────────────────────────────────────

def _check_prerequisites(require_uv: bool = True, require_node: bool = False):
    issues = []
    if require_uv and not shutil.which("uv"):
        issues.append("  uv not found. Install: curl -LsSf https://astral.sh/uv/install.sh | sh")
    if require_node and not shutil.which("node"):
        issues.append("  node not found. Install: https://nodejs.org")
    if issues:
        print("⚠ Missing prerequisites:\n")
        for i in issues:
            print(i)
        print()


def _install_backend(be_path: Path):
    if not shutil.which("uv"):
        print("  ⏭ Skipping backend install (uv not found)")
        print("    Install uv, then: cd backend && uv sync")
        return

    print("  🐍 Backend: uv sync...")
    try:
        result = subprocess.run(
            ["uv", "sync"], cwd=str(be_path),
            capture_output=True, text=True, timeout=120,
        )
        if result.returncode == 0:
            print("  ✅ Backend dependencies installed")
        else:
            print(f"  ⚠ uv sync issue: {result.stderr[:200]}")
            print(f"    Run manually: cd backend && uv sync")
    except (subprocess.TimeoutExpired, Exception) as e:
        print(f"  ⚠ Install error: {e}")


def _install_frontend(fe_path: Path):
    if not shutil.which("npm"):
        print("  ⏭ Skipping frontend install (npm not found)")
        print("    Install Node.js, then: cd frontend && npm install")
        return

    print("  📦 Frontend: npm install...")
    try:
        result = subprocess.run(
            ["npm", "install"], cwd=str(fe_path),
            capture_output=True, text=True, timeout=120,
        )
        if result.returncode == 0:
            print("  ✅ Frontend dependencies installed")
        else:
            print(f"  ⚠ npm install issue: {result.stderr[:200]}")
    except (subprocess.TimeoutExpired, Exception) as e:
        print(f"  ⚠ Install error: {e}")


def _write(path: Path, content: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        return
    path.write_text(content)
    print(f"  ✅ {path}")
