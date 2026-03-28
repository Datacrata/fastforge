# ⚡ FastForge

**Full-stack application framework for FastAPI + React (optional)**

Runtime framework + pre-built modules + CLI tooling + auto-generated frontend clients. Supports PostgreSQL, MySQL, SQLite, and MongoDB.

## Quick Start

```bash
# Install FastForge
pip install -e .              # CLI
pip install -e backend/       # Runtime

# Create project (FastAPI backend only)
fastforge init my-app

# Or with a specific database
fastforge init my-app --db mysql
fastforge init my-app --db mongodb
fastforge init my-app --db sqlite

# Or with React frontend included
fastforge init my-app --react
fastforge init my-app --db postgres --react

# Create & edit models
cd my-app
fastforge crud product       # creates model stub
# Edit backend/app/models/product.py

# Generate code from model
fastforge generate product

# Start backend
cd backend && uv run uvicorn app.main:app --reload
# → http://localhost:8000/api/v1/docs
# → Admin: admin@fastforge.dev / admin123

# Add React frontend later (if not created with --react)
fastforge add-frontend

# Sync frontend TypeScript client
fastforge generate-client -i http://localhost:8000/api/v1/openapi.json

# Start frontend
cd frontend && npm run dev
# → http://localhost:5173
```

## Workflow

```
fastforge crud product          → creates model stub
you edit the model               → add columns, ForeignKeys
fastforge migrate               → create DB migration
fastforge generate product      → generates schemas, repo, service, router
fastforge generate-client       → generates TypeScript types + hooks
```

## CLI Commands

| Command | What it does |
|---------|-------------|
| `fastforge init <name>` | Scaffold project with FastAPI backend |
| `fastforge init <name> --react` | Scaffold with React frontend included |
| `fastforge init <name> --db <db>` | Choose database: `postgres`, `mysql`, `sqlite`, `mongodb` |
| `fastforge add-frontend` | Add React frontend to existing project |
| `fastforge crud <entity>` | Create model stub |
| `fastforge generate <entity>` | Generate schemas/repo/service/router from model |
| `fastforge generate --all` | Generate for ALL models |
| `fastforge generate --force` | Overwrite service + router too |
| `fastforge migrate` | Create Alembic migration |
| `fastforge generate-client -i <url>` | Generate TypeScript client from OpenAPI |
| `fastforge list` | Show all models and status |

## Supported Databases

| Database | Driver | Connection URL |
|----------|--------|----------------|
| PostgreSQL (default) | `psycopg2-binary` | `postgresql://localhost/fastforge_db` |
| MySQL | `pymysql` | `mysql+pymysql://root:password@localhost/fastforge_db` |
| SQLite | built-in | `sqlite:///./app.db` |
| MongoDB | `motor` + `beanie` | `mongodb://localhost:27017/fastforge_db` |

## What `fastforge generate` creates

| File | Regenerated? | Purpose |
|------|-------------|---------|
| schemas/{entity}.py | Always | Pydantic Create/Update/Response/List |
| repositories/{entity}_repository.py | Always | GenericRepository with search fields |
| permissions/{entity}.py | Always | PermissionGroup |
| services/{entity}_service.py | Once (preserved) | CrudAppService + your custom hooks |
| api/routes/{entity}.py | Once (preserved) | REST endpoints + your custom endpoints |

## Pre-built Modules

**Identity** — register, login, refresh, me, change-password, user CRUD, role CRUD with permissions

**Tenant Management** — tenant CRUD + per-tenant feature flags

**Data Seeding** — auto-creates admin user + default roles on startup

## Runtime Features

| Feature | Usage |
|---------|-------|
| Entity base classes | `FullAuditedEntity` — auto id, audit fields, soft delete |
| Generic repository | Pagination, search, sort, soft-delete filter, tenant filter |
| CRUD service | Lifecycle hooks: before_create, after_create, before_update, etc. |
| Permissions | `@require_permission("Product.Create")` |
| JWT auth | AuthMiddleware auto-populates request.state |
| Domain events | `event_bus.publish(OrderCreated(...))` |
| Background jobs | `job_manager.enqueue(SendEmail, ...)` |
| Settings | `settings.get("key", tenant_id="t-1")` — global→tenant→user |
| Exceptions | `raise BusinessException("reason")` → standardized JSON |

## Frontend (optional, auto-generated)

Add React frontend at project creation with `--react`, or later with `fastforge add-frontend`.

```tsx
import { useListProducts, useCreateProduct, useAuth, RequirePermission } from "./api";

function Products() {
  const { data } = useListProducts({ params: { search: "phone" } });
  const create = useCreateProduct();

  return (
    <RequirePermission permission="Product.Read">
      {data?.items.map(p => <div key={p.id}>{p.name}</div>)}
    </RequirePermission>
  );
}
```
