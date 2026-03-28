"""
Model Introspector
====================
Reads a SQLAlchemy model .py file and extracts field information.
This is what makes `fastforge generate <entity>` work — it reads
your model (the source of truth) and generates everything else from it.

Two modes:
  1. AST parsing — reads the .py file statically (no import needed)
  2. Runtime inspection — imports the model class and inspects SQLAlchemy columns

We use AST parsing as the primary approach because it doesn't require
the full app to be importable (no dependency chain issues).
"""
from __future__ import annotations
import ast
import re
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ColumnInfo:
    """Extracted info about a single model column."""
    name: str
    sa_type: str          # "String(255)", "Integer", "Float", etc.
    python_type: str      # "str", "int", "float", etc.
    nullable: bool = True
    is_primary_key: bool = False
    has_default: bool = False
    is_foreign_key: bool = False
    fk_target: Optional[str] = None  # "users.id"
    max_length: Optional[int] = None
    description: str = ""


@dataclass
class ModelInfo:
    """Complete extracted info about a model class."""
    class_name: str
    table_name: str
    base_class: str       # "FullAuditedEntity", "AuditedEntity", "Entity", etc.
    columns: list[ColumnInfo] = field(default_factory=list)
    searchable_fields: list[str] = field(default_factory=list)
    file_path: str = ""

    @property
    def has_soft_delete(self) -> bool:
        return self.base_class in ("SoftDeleteEntity", "FullAuditedEntity")

    @property
    def has_audit(self) -> bool:
        return self.base_class in ("AuditedEntity", "SoftDeleteEntity", "FullAuditedEntity")

    @property
    def has_tenant(self) -> bool:
        return any(c.name == "tenant_id" for c in self.columns)

    @property
    def user_columns(self) -> list[ColumnInfo]:
        """Columns defined by the user (excluding id, audit fields, soft delete)."""
        skip = {
            "id", "created_at", "updated_at", "created_by", "updated_by",
            "is_deleted", "deleted_at", "deleted_by", "tenant_id",
        }
        return [c for c in self.columns if c.name not in skip and not c.is_primary_key]


# ─── SA Type → Python Type Mapping ──────────────────────────────────────────

SA_TO_PYTHON = {
    "String": "str",
    "Text": "str",
    "Integer": "int",
    "BigInteger": "int",
    "SmallInteger": "int",
    "Float": "float",
    "Numeric": "float",
    "Boolean": "bool",
    "Date": "date",
    "DateTime": "datetime",
    "Time": "time",
    "UUID": "UUID",
    "JSON": "dict",
    "LargeBinary": "bytes",
    "Enum": "str",
}


# ─── AST-Based Parser ───────────────────────────────────────────────────────

def introspect_model_file(file_path: str) -> Optional[ModelInfo]:
    """
    Parse a model .py file using AST and extract column information.
    This is the primary introspection method — works without importing.
    """
    path = Path(file_path)
    if not path.exists():
        return None

    source = path.read_text()
    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        print(f"  ⚠ Syntax error in {file_path}: {e}")
        return None

    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue

        # Check if it's a model class (has __tablename__)
        table_name = _extract_tablename(node)
        if not table_name:
            continue

        # Get base class
        base_class = _extract_base_class(node)

        info = ModelInfo(
            class_name=node.name,
            table_name=table_name,
            base_class=base_class,
            file_path=file_path,
        )

        # Extract columns
        for item in node.body:
            if isinstance(item, ast.Assign):
                col = _parse_column_assign(item)
                if col:
                    info.columns.append(col)

            # Check for __searchable__
            if isinstance(item, ast.Assign):
                for target in item.targets:
                    if isinstance(target, ast.Name) and target.id == "__searchable__":
                        info.searchable_fields = _extract_list_values(item.value)

        return info

    return None


def introspect_models_dir(models_dir: str) -> list[ModelInfo]:
    """Introspect all model files in a directory."""
    models = []
    path = Path(models_dir)
    if not path.exists():
        return models

    for py_file in sorted(path.glob("*.py")):
        if py_file.name.startswith("_"):
            continue
        info = introspect_model_file(str(py_file))
        if info:
            models.append(info)

    return models


# ─── AST Helpers ─────────────────────────────────────────────────────────────

def _extract_tablename(class_node: ast.ClassDef) -> Optional[str]:
    """Extract __tablename__ from a class body."""
    for item in class_node.body:
        if isinstance(item, ast.Assign):
            for target in item.targets:
                if isinstance(target, ast.Name) and target.id == "__tablename__":
                    if isinstance(item.value, ast.Constant):
                        return item.value.value
    return None


def _extract_base_class(class_node: ast.ClassDef) -> str:
    """Extract the primary base class name."""
    for base in class_node.bases:
        if isinstance(base, ast.Name):
            if base.id in ("Entity", "AuditedEntity", "SoftDeleteEntity", "FullAuditedEntity"):
                return base.id
        if isinstance(base, ast.Attribute):
            return base.attr
    return "Base"


def _parse_column_assign(node: ast.Assign) -> Optional[ColumnInfo]:
    """Parse a line like: name = Column(String(255), nullable=False)"""
    if len(node.targets) != 1:
        return None
    target = node.targets[0]
    if not isinstance(target, ast.Name):
        return None

    col_name = target.id

    # Must be a Column() call
    if not isinstance(node.value, ast.Call):
        return None

    func = node.value.func
    if isinstance(func, ast.Name) and func.id != "Column":
        return None
    if isinstance(func, ast.Attribute) and func.attr != "Column":
        return None
    if not (isinstance(func, ast.Name) or isinstance(func, ast.Attribute)):
        return None

    args = node.value.args
    kwargs = {kw.arg: kw.value for kw in node.value.keywords if kw.arg}

    # Extract SA type from first positional arg
    sa_type = "String"
    max_length = None
    if args:
        sa_type, max_length = _parse_sa_type(args[0])

    # Extract Column options
    nullable = True
    is_pk = False
    has_default = False
    is_fk = False
    fk_target = None

    if "nullable" in kwargs:
        nullable = _is_true(kwargs["nullable"])
    if "primary_key" in kwargs:
        is_pk = _is_true(kwargs["primary_key"])
    if "default" in kwargs:
        has_default = True

    # Check for ForeignKey in args
    for arg in args:
        if isinstance(arg, ast.Call):
            arg_func = arg.func
            if isinstance(arg_func, ast.Name) and arg_func.id == "ForeignKey":
                is_fk = True
                if arg.args and isinstance(arg.args[0], ast.Constant):
                    fk_target = arg.args[0].value

    # Map SA type to Python type
    base_sa = sa_type.split("(")[0]
    python_type = SA_TO_PYTHON.get(base_sa, "str")

    return ColumnInfo(
        name=col_name,
        sa_type=sa_type,
        python_type=python_type,
        nullable=nullable,
        is_primary_key=is_pk,
        has_default=has_default,
        is_foreign_key=is_fk,
        fk_target=fk_target,
        max_length=max_length,
    )


def _parse_sa_type(node: ast.expr) -> tuple[str, Optional[int]]:
    """Parse a SQLAlchemy type like String(255) or Integer."""
    if isinstance(node, ast.Name):
        return node.id, None
    if isinstance(node, ast.Call):
        if isinstance(node.func, ast.Name):
            type_name = node.func.id
            # Extract length if present
            max_length = None
            if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, int):
                max_length = node.args[0].value
            # Reconstruct type string
            arg_strs = []
            for arg in node.args:
                if isinstance(arg, ast.Constant):
                    arg_strs.append(str(arg.value))
            if arg_strs:
                return f"{type_name}({', '.join(arg_strs)})", max_length
            return type_name, max_length
    if isinstance(node, ast.Attribute):
        return node.attr, None
    return "String", None


def _is_true(node: ast.expr) -> bool:
    if isinstance(node, ast.Constant):
        return bool(node.value)
    if isinstance(node, ast.Name):
        return node.id == "True"
    return False


def _extract_list_values(node: ast.expr) -> list[str]:
    """Extract string values from a list literal like ["name", "email"]."""
    if isinstance(node, ast.List):
        return [
            elt.value for elt in node.elts
            if isinstance(elt, ast.Constant) and isinstance(elt.value, str)
        ]
    return []
