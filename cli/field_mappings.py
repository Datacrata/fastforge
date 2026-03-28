"""
FastForge Field Mappings & Utilities
=======================================
Shared constants and helpers for the CRUD generator.
"""
from __future__ import annotations
import re

# ─── Field Type Mappings ─────────────────────────────────────────────────────

PYTHON_TYPES = {
    "str": "str", "string": "str",
    "int": "int", "integer": "int",
    "float": "float", "decimal": "float",
    "bool": "bool", "boolean": "bool",
    "date": "date", "datetime": "datetime",
    "text": "str", "email": "str", "uuid": "UUID",
}

SQLALCHEMY_TYPES = {
    "str": "String(255)", "string": "String(255)",
    "int": "Integer", "integer": "Integer",
    "float": "Float", "decimal": "Numeric(10, 2)",
    "bool": "Boolean", "boolean": "Boolean",
    "date": "Date", "datetime": "DateTime(timezone=True)",
    "text": "Text", "email": "String(320)", "uuid": "UUID",
}

SA_IMPORT_MAP = {
    "str": "String", "string": "String",
    "int": "Integer", "integer": "Integer",
    "float": "Float", "decimal": "Numeric",
    "bool": "Boolean", "boolean": "Boolean",
    "date": "Date", "datetime": "DateTime",
    "text": "Text", "email": "String", "uuid": "UUID",
}


# ─── Name Conversions ────────────────────────────────────────────────────────

def to_snake(name: str) -> str:
    s = re.sub(r'(.)([A-Z][a-z]+)', r'\1_\2', name)
    return re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', s).lower().replace("-", "_")

def to_pascal(name: str) -> str:
    return "".join(w.capitalize() for w in re.split(r'[_\-\s]+', name))

def to_camel(name: str) -> str:
    p = to_pascal(name)
    return p[0].lower() + p[1:] if p else ""

def to_kebab(name: str) -> str:
    return to_snake(name).replace("_", "-")

def pluralize(name: str) -> str:
    if name.endswith("y") and name[-2] not in "aeiou":
        return name[:-1] + "ies"
    if name.endswith(("s", "sh", "ch", "x", "z")):
        return name + "es"
    return name + "s"


# ─── Field Parsing ───────────────────────────────────────────────────────────

def parse_fields(field_args: list[str]) -> list[dict]:
    """Parse 'name:str' 'price:float' 'bio:text?' into structured dicts."""
    fields = []
    for f in field_args:
        optional = f.endswith("?")
        f = f.rstrip("?")
        parts = f.split(":")
        if len(parts) != 2:
            print(f"  ⚠ Skipping invalid field: '{f}' (use name:type)")
            continue
        name, ftype = parts
        ftype = ftype.lower()
        if ftype not in PYTHON_TYPES:
            print(f"  ⚠ Unknown type '{ftype}' for '{name}', defaulting to 'str'")
            ftype = "str"
        fields.append({
            "name": to_snake(name),
            "type": ftype,
            "optional": optional,
            "python_type": PYTHON_TYPES[ftype],
            "sa_type": SQLALCHEMY_TYPES[ftype],
            "sa_import": SA_IMPORT_MAP[ftype],
        })
    return fields
