"""
Generate From Model (v2 — safe regeneration)
===============================================
Reads an existing SQLAlchemy model file and generates:

  ALWAYS regenerated (safe to overwrite — derived from model):
    - schemas/{entity}.py
    - repositories/{entity}_repository.py
    - permissions/{entity}.py

  GENERATED ONCE (user customizes these — never overwritten):
    - services/{entity}_service.py
    - api/routes/{entity}.py

This means you can:
  1. Edit the model (add columns)
  2. Run `fastforge generate product`
  3. Schemas + repo update automatically
  4. Your custom business logic in service/router is preserved

To force-regenerate service/router: fastforge generate product --force
"""
from __future__ import annotations
import os
import re
from pathlib import Path
from .model_introspector import ModelInfo, ColumnInfo, introspect_model_file

PYDANTIC_TYPE_MAP = {
    "str": "str", "int": "int", "float": "float", "bool": "bool",
    "date": "date", "datetime": "datetime", "time": "time",
    "UUID": "UUID", "dict": "dict", "bytes": "bytes",
}


def generate_from_model(model_path: str, base_path: str, force: bool = False) -> list[str]:
    """
    Read a model file and generate all supporting files.
    
    Args:
        force: If True, overwrite service and router even if they exist.
    """
    info = introspect_model_file(model_path)
    if not info:
        print(f"  ❌ Could not parse model from: {model_path}")
        return []

    snake = _to_snake(info.class_name)
    pascal = info.class_name
    plural = _pluralize(snake)
    cols = info.user_columns

    print(f"\n  Model: {pascal} ({info.table_name})")
    print(f"  Base:  {info.base_class} (audit={info.has_audit}, soft_delete={info.has_soft_delete})")
    print(f"  Fields: {', '.join(c.name + ':' + c.python_type for c in cols)}")
    print()

    created = []

    # ── ALWAYS regenerated (derived from model, no custom code) ──────────
    created.append(_gen_schemas(snake, pascal, plural, cols, info, base_path))
    created.append(_gen_permissions(snake, pascal, base_path))
    created.append(_gen_repository(snake, pascal, info, base_path))

    # ── GENERATED ONCE (user customizable — skip if exists) ──────────────
    svc_path = f"{base_path}/app/services/{snake}_service.py"
    route_path = f"{base_path}/app/api/routes/{snake}.py"

    if force or not os.path.exists(svc_path):
        created.append(_gen_service(snake, pascal, info, base_path, overwrite=force))
    else:
        print(f"  ⏭ Preserved: {svc_path}")

    if force or not os.path.exists(route_path):
        created.append(_gen_router(snake, pascal, plural, cols, info, base_path, overwrite=force))
    else:
        print(f"  ⏭ Preserved: {route_path}")

    _register_router(snake, pascal, base_path)

    return [c for c in created if c]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _gen_schemas(snake, pascal, plural, cols: list[ColumnInfo], info: ModelInfo, base_path) -> str:
    py_imports = set()
    for c in cols:
        if c.python_type == "date": py_imports.add("from datetime import date")
        if c.python_type == "datetime": py_imports.add("from datetime import datetime")
        if c.python_type == "time": py_imports.add("from datetime import time")
        if c.python_type == "UUID": py_imports.add("from uuid import UUID")

    create_fields = []
    update_fields = []
    response_fields = []

    for c in cols:
        pt = PYDANTIC_TYPE_MAP.get(c.python_type, "str")
        if c.nullable or c.has_default:
            create_fields.append(f"    {c.name}: Optional[{pt}] = None")
        else:
            create_fields.append(f"    {c.name}: {pt}")
        update_fields.append(f"    {c.name}: Optional[{pt}] = None")
        if c.nullable:
            response_fields.append(f"    {c.name}: Optional[{pt}] = None")
        else:
            response_fields.append(f"    {c.name}: {pt}")

    audit_response = ""
    if info.has_audit:
        audit_response = """    created_at: datetime
    updated_at: datetime
    created_by: Optional[str] = None
    updated_by: Optional[str] = None"""
        py_imports.add("from datetime import datetime")

    content = f'''"""
{pascal} Schemas
Auto-generated from model — safe to regenerate.
"""
from typing import Optional, List
from pydantic import BaseModel, ConfigDict
{chr(10).join(sorted(py_imports))}


class {pascal}Create(BaseModel):
{chr(10).join(create_fields) if create_fields else "    pass"}


class {pascal}Update(BaseModel):
{chr(10).join(update_fields) if update_fields else "    pass"}


class {pascal}Response(BaseModel):
    id: int
{chr(10).join(response_fields)}
{audit_response}
    model_config = ConfigDict(from_attributes=True)


class {pascal}ListResponse(BaseModel):
    items: List[{pascal}Response]
    total: int
    page: int
    page_size: int
    total_pages: int
'''
    return _write_always(f"{base_path}/app/schemas/{snake}.py", content)


def _gen_permissions(snake, pascal, base_path) -> str:
    content = f'''"""
{pascal} Permissions
Auto-generated from model — safe to regenerate.
"""
from fastforge_core import PermissionGroup

{pascal}Permissions = PermissionGroup("{pascal}", [
    "Create", "Read", "Update", "Delete", "Export",
])
'''
    return _write_always(f"{base_path}/app/permissions/{snake}.py", content)


def _gen_repository(snake, pascal, info: ModelInfo, base_path) -> str:
    search_fields = [f'"{f}"' for f in info.searchable_fields]
    if not search_fields:
        search_fields = [
            f'"{c.name}"' for c in info.user_columns
            if c.python_type == "str" and c.name not in ("password_hash", "token")
        ]

    content = f'''"""
{pascal} Repository
Auto-generated from model — safe to regenerate.
"""
from fastforge_core import GenericRepository
from app.models.{snake} import {pascal}


class {pascal}Repository(GenericRepository[{pascal}]):
    searchable_fields = [{", ".join(search_fields)}]
    default_sort_field = "id"
    default_sort_order = "desc"
'''
    return _write_always(f"{base_path}/app/repositories/{snake}_repository.py", content)


def _gen_service(snake, pascal, info: ModelInfo, base_path, overwrite=False) -> str:
    content = f'''"""
{pascal} Service
Generated once — YOUR custom business logic goes here.
This file is NOT overwritten when you re-run `fastforge generate`.
"""
from sqlalchemy.orm import Session
from typing import Optional

from fastforge_core import CrudAppService
from app.models.{snake} import {pascal}
from app.schemas.{snake} import {pascal}Create, {pascal}Update, {pascal}Response
from app.repositories.{snake}_repository import {pascal}Repository


class {pascal}Service(CrudAppService[{pascal}, {pascal}Create, {pascal}Update, {pascal}Response]):

    def __init__(self, db: Session, user_id: Optional[str] = None, tenant_id: Optional[str] = None):
        repo = {pascal}Repository(db, {pascal}, user_id, tenant_id)
        super().__init__(repo, {pascal}Response)

    # ─── Add your custom business logic below ────────────────────────────
    #
    # Override any of these hooks:
    #
    # def before_create(self, data: {pascal}Create):
    #     \"\"\"Validate before creating.\"\"\"
    #     if some_condition:
    #         raise BusinessException("Cannot create: reason")
    #
    # def after_create(self, entity: {pascal}):
    #     \"\"\"Do something after creation (send email, publish event, etc.)\"\"\"
    #     event_bus.publish(ProductCreated(id=entity.id))
    #
    # def before_update(self, entity: {pascal}, data: {pascal}Update):
    #     \"\"\"Validate before updating.\"\"\"
    #     pass
    #
    # def before_delete(self, entity: {pascal}):
    #     \"\"\"Prevent deletion if entity has dependencies.\"\"\"
    #     pass
    #
    # def map_to_response(self, entity: {pascal}) -> {pascal}Response:
    #     \"\"\"Add computed fields to response.\"\"\"
    #     response = super().map_to_response(entity)
    #     return response
'''
    writer = _write_always if overwrite else _write_once
    return writer(f"{base_path}/app/services/{snake}_service.py", content)


def _gen_router(snake, pascal, plural, cols: list[ColumnInfo], info: ModelInfo, base_path, overwrite=False) -> str:
    kebab_plural = plural.replace("_", "-")

    filter_params = []
    filter_dict = []
    for c in cols:
        if c.python_type == "bool":
            filter_params.append(f"    {c.name}: Optional[bool] = Query(None),")
            filter_dict.append(f'"{c.name}": {c.name}')
        elif c.is_foreign_key or c.name.endswith("_id"):
            filter_params.append(f"    {c.name}: Optional[int] = Query(None),")
            filter_dict.append(f'"{c.name}": {c.name}')

    filter_params_str = "\n" + "\n".join(filter_params) if filter_params else ""
    filters_arg = f"filters={{{', '.join(filter_dict)}}}," if filter_dict else ""

    content = f'''"""
{pascal} Routes
Generated once — YOUR custom endpoints go here.
This file is NOT overwritten when you re-run `fastforge generate`.
"""
from typing import Optional, List
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.services.{snake}_service import {pascal}Service
from app.schemas.{snake} import (
    {pascal}Create, {pascal}Update, {pascal}Response, {pascal}ListResponse,
)

router = APIRouter(prefix="/{kebab_plural}", tags=["{pascal}"])


def _svc(db: Session = Depends(get_db)) -> {pascal}Service:
    return {pascal}Service(db)


@router.get("/", response_model={pascal}ListResponse)
def list_{plural}(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None),
    sort_by: str = Query("id"),
    sort_order: str = Query("desc", pattern="^(asc|desc)$"),{filter_params_str}
    service: {pascal}Service = Depends(_svc),
):
    return service.get_list(
        page=page, page_size=page_size,
        search=search, sort_by=sort_by, sort_order=sort_order,
        {filters_arg}
    )


@router.get("/{{id}}", response_model={pascal}Response)
def get_{snake}(id: int, service: {pascal}Service = Depends(_svc)):
    return service.get(id)


@router.post("/", response_model={pascal}Response, status_code=201)
def create_{snake}(data: {pascal}Create, service: {pascal}Service = Depends(_svc)):
    return service.create(data)


@router.put("/{{id}}", response_model={pascal}Response)
def update_{snake}(id: int, data: {pascal}Update, service: {pascal}Service = Depends(_svc)):
    return service.update(id, data)


@router.delete("/{{id}}")
def delete_{snake}(id: int, service: {pascal}Service = Depends(_svc)):
    return service.delete(id)


@router.post("/bulk-delete")
def bulk_delete_{plural}(ids: List[int], service: {pascal}Service = Depends(_svc)):
    return service.bulk_delete(ids)

# ─── Add your custom endpoints below ────────────────────────────────────
#
# @router.get("/stats")
# def get_{snake}_stats(service: {pascal}Service = Depends(_svc)):
#     return {{"total": service.repo.count()}}
'''
    writer = _write_always if overwrite else _write_once
    return writer(f"{base_path}/app/api/routes/{snake}.py", content)


def _register_router(snake, pascal, base_path):
    router_file = f"{base_path}/app/api/router.py"
    if not os.path.exists(router_file):
        return
    with open(router_file) as f:
        content = f.read()

    import_line = f"from app.api.routes.{snake} import router as {snake}_router"
    include_line = f"api_router.include_router({snake}_router)"

    if import_line in content:
        return  # Already registered, silent skip

    content = content.replace(
        "# FASTFORGE_ROUTER_IMPORTS",
        f"{import_line}\n# FASTFORGE_ROUTER_IMPORTS"
    )
    content = content.replace(
        "# FASTFORGE_ROUTER_INCLUDES",
        f"{include_line}\n# FASTFORGE_ROUTER_INCLUDES"
    )
    with open(router_file, "w") as f:
        f.write(content)
    print(f"  ✅ Registered router: {snake}")


# ─── File Writers ────────────────────────────────────────────────────────────

def _write_always(path: str, content: str) -> str:
    """Write file, always overwriting. For derived files (schemas, repo, perms)."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    existed = os.path.exists(path)
    with open(path, "w") as f:
        f.write(content)
    print(f"  ✅ {'Updated' if existed else 'Created'}: {path}")
    return path


def _write_once(path: str, content: str) -> str:
    """Write file only if it doesn't exist. For user-customizable files."""
    if os.path.exists(path):
        print(f"  ⏭ Preserved: {path}")
        return path
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(content)
    print(f"  ✅ Created: {path}")
    return path


def _to_snake(name):
    s = re.sub(r'(.)([A-Z][a-z]+)', r'\1_\2', name)
    return re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', s).lower()


def _pluralize(name):
    if name.endswith("y") and name[-2] not in "aeiou":
        return name[:-1] + "ies"
    if name.endswith(("s", "sh", "ch", "x", "z")):
        return name + "es"
    return name + "s"
