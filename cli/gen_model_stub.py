"""
Model Stub Generator
======================
`fastforge crud product` generates ONLY the model file.
You then edit it, run migrate, then run `fastforge generate product`.
"""
from __future__ import annotations
import os
from .field_mappings import to_snake, to_pascal, pluralize


def generate_model_stub(entity: str, base_path: str) -> str:
    """
    Generate a model stub file for the user to fill in.
    Returns the file path.
    """
    snake = to_snake(entity)
    pascal = to_pascal(entity)
    plural = pluralize(snake)

    content = f'''"""
{pascal} Model
Define your columns below. Then run:
  1. fastforge migrate          — create database migration
  2. fastforge generate {snake}  — generate schemas, repo, service, router
"""
from sqlalchemy import Column, String, Integer, Float, Boolean, Text, DateTime, Date, Numeric, ForeignKey
from fastforge_core import FullAuditedEntity


class {pascal}(FullAuditedEntity):
    __tablename__ = "{plural}"

    # ── Define your columns here ─────────────────────────────────────────
    name = Column(String(255), nullable=False)

    # Examples (uncomment / modify as needed):
    # description = Column(Text, nullable=True)
    # price = Column(Numeric(10, 2), nullable=False)
    # quantity = Column(Integer, default=0)
    # is_active = Column(Boolean, default=True, nullable=False)
    # email = Column(String(320), nullable=False, unique=True)
    # category_id = Column(Integer, ForeignKey("categories.id"), nullable=True)
    # published_at = Column(DateTime(timezone=True), nullable=True)

    # ── Searchable fields (used by GenericRepository for text search) ────
    __searchable__ = ["name"]
'''

    path = f"{base_path}/app/models/{snake}.py"
    if os.path.exists(path):
        print(f"  ⏭ Model already exists: {path}")
        print(f"  Edit it, then run: fastforge generate {snake}")
        return path

    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(content)
    print(f"  ✅ Created: {path}")
    return path
