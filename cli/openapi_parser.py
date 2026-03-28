"""
OpenAPI Spec Parser
====================
Reads an OpenAPI 3.x spec (JSON or YAML) and extracts structured data
that the code generators consume.

This is the "brain" of generate-client — it understands the OpenAPI spec
and produces a normalized intermediate representation.
"""
from __future__ import annotations
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse


# ─── Data Models (Intermediate Representation) ──────────────────────────────

@dataclass
class PropertyInfo:
    name: str
    ts_type: str
    required: bool
    description: str = ""
    format: str = ""
    is_array: bool = False
    is_enum: bool = False
    enum_values: list[str] = field(default_factory=list)
    nullable: bool = False
    default: Optional[str] = None


@dataclass
class SchemaInfo:
    """Represents a Pydantic model → TypeScript interface."""
    name: str
    properties: list[PropertyInfo] = field(default_factory=list)
    description: str = ""
    is_enum: bool = False
    enum_values: list[str] = field(default_factory=list)
    extends: Optional[str] = None


@dataclass
class ParameterInfo:
    name: str
    ts_type: str
    required: bool
    location: str  # "query" | "path" | "header"
    description: str = ""
    default: Optional[str] = None


@dataclass
class EndpointInfo:
    """Represents a single API endpoint → service function + hook."""
    operation_id: str
    method: str  # GET, POST, PUT, DELETE, PATCH
    path: str
    tag: str
    summary: str = ""
    description: str = ""
    parameters: list[ParameterInfo] = field(default_factory=list)
    request_body_type: Optional[str] = None
    request_body_required: bool = False
    response_type: Optional[str] = None
    response_is_array: bool = False
    response_is_paginated: bool = False
    is_mutation: bool = False  # POST/PUT/DELETE/PATCH


@dataclass
class TagGroup:
    """Endpoints grouped by tag → one service file per tag."""
    tag: str
    description: str = ""
    endpoints: list[EndpointInfo] = field(default_factory=list)


@dataclass
class ParsedSpec:
    """The complete parsed result — everything generators need."""
    title: str
    version: str
    base_url: str
    schemas: list[SchemaInfo] = field(default_factory=list)
    tag_groups: list[TagGroup] = field(default_factory=list)
    all_endpoints: list[EndpointInfo] = field(default_factory=list)


# ─── Type Mapping ────────────────────────────────────────────────────────────

def openapi_type_to_ts(schema: dict, spec: dict) -> str:
    """Convert an OpenAPI schema object to a TypeScript type string."""
    if not schema:
        return "unknown"

    # Handle $ref
    if "$ref" in schema:
        return ref_to_name(schema["$ref"])

    # Handle allOf (inheritance / composition)
    if "allOf" in schema:
        types = [openapi_type_to_ts(s, spec) for s in schema["allOf"]]
        return " & ".join(types) if len(types) > 1 else types[0]

    # Handle oneOf / anyOf
    if "oneOf" in schema:
        types = [openapi_type_to_ts(s, spec) for s in schema["oneOf"]]
        return " | ".join(types)
    if "anyOf" in schema:
        # Filter out null types for nullable handling
        non_null = [s for s in schema["anyOf"] if s.get("type") != "null"]
        null_present = len(non_null) < len(schema["anyOf"])
        if len(non_null) == 1:
            base = openapi_type_to_ts(non_null[0], spec)
            return f"{base} | null" if null_present else base
        types = [openapi_type_to_ts(s, spec) for s in non_null]
        result = " | ".join(types)
        return f"({result}) | null" if null_present else result

    schema_type = schema.get("type", "")
    schema_format = schema.get("format", "")

    # Arrays
    if schema_type == "array":
        items = schema.get("items", {})
        item_type = openapi_type_to_ts(items, spec)
        return f"{item_type}[]"

    # Primitives
    if schema_type == "string":
        if "enum" in schema:
            return " | ".join(f'"{v}"' for v in schema["enum"])
        return "string"
    if schema_type == "integer" or schema_type == "number":
        return "number"
    if schema_type == "boolean":
        return "boolean"
    if schema_type == "null":
        return "null"
    if schema_type == "object":
        # Inline object with properties
        if "properties" in schema:
            props = []
            required_set = set(schema.get("required", []))
            for pname, pschema in schema["properties"].items():
                ptype = openapi_type_to_ts(pschema, spec)
                opt = "" if pname in required_set else "?"
                props.append(f"{pname}{opt}: {ptype}")
            return "{ " + "; ".join(props) + " }"
        # additionalProperties
        if "additionalProperties" in schema:
            val_type = openapi_type_to_ts(schema["additionalProperties"], spec)
            return f"Record<string, {val_type}>"
        return "Record<string, unknown>"

    return "unknown"


def ref_to_name(ref: str) -> str:
    """Extract type name from $ref like '#/components/schemas/Product'."""
    return ref.split("/")[-1]


# ─── Main Parser ─────────────────────────────────────────────────────────────

def parse_openapi(spec_data: dict) -> ParsedSpec:
    """Parse a full OpenAPI 3.x spec dict into our intermediate representation."""

    info = spec_data.get("info", {})
    servers = spec_data.get("servers", [])
    base_url = servers[0]["url"] if servers else ""

    result = ParsedSpec(
        title=info.get("title", "API"),
        version=info.get("version", "1.0.0"),
        base_url=base_url,
    )

    # ── Parse Schemas ────────────────────────────────────────────────────
    components = spec_data.get("components", {})
    schemas_raw = components.get("schemas", {})

    for schema_name, schema_def in schemas_raw.items():
        # Skip internal schemas
        if schema_name.startswith("_"):
            continue

        # Check if it's an enum
        if "enum" in schema_def:
            result.schemas.append(SchemaInfo(
                name=schema_name,
                is_enum=True,
                enum_values=schema_def["enum"],
                description=schema_def.get("description", ""),
            ))
            continue

        # Regular object schema
        schema_info = SchemaInfo(
            name=schema_name,
            description=schema_def.get("description", ""),
        )

        # Handle allOf (inheritance)
        if "allOf" in schema_def:
            for sub in schema_def["allOf"]:
                if "$ref" in sub:
                    schema_info.extends = ref_to_name(sub["$ref"])
                elif "properties" in sub:
                    required_set = set(sub.get("required", []))
                    for pname, pschema in sub["properties"].items():
                        schema_info.properties.append(_parse_property(
                            pname, pschema, pname in required_set, spec_data
                        ))

        # Direct properties
        required_set = set(schema_def.get("required", []))
        for pname, pschema in schema_def.get("properties", {}).items():
            schema_info.properties.append(_parse_property(
                pname, pschema, pname in required_set, spec_data
            ))

        result.schemas.append(schema_info)

    # ── Parse Endpoints ──────────────────────────────────────────────────
    paths = spec_data.get("paths", {})
    tag_map: dict[str, TagGroup] = {}

    for path, path_item in paths.items():
        for method in ("get", "post", "put", "delete", "patch", "head", "options"):
            if method not in path_item:
                continue

            operation = path_item[method]
            tags = operation.get("tags", ["Default"])
            tag = tags[0] if tags else "Default"
            operation_id = operation.get("operationId", f"{method}_{path}")

            # Clean operation_id
            operation_id = _clean_operation_id(operation_id)

            endpoint = EndpointInfo(
                operation_id=operation_id,
                method=method.upper(),
                path=path,
                tag=tag,
                summary=operation.get("summary", ""),
                description=operation.get("description", ""),
                is_mutation=method in ("post", "put", "delete", "patch"),
            )

            # Parameters
            params = operation.get("parameters", []) + path_item.get("parameters", [])
            for param in params:
                if "$ref" in param:
                    param = _resolve_ref(param["$ref"], spec_data)
                param_schema = param.get("schema", {})
                endpoint.parameters.append(ParameterInfo(
                    name=param["name"],
                    ts_type=openapi_type_to_ts(param_schema, spec_data),
                    required=param.get("required", False),
                    location=param.get("in", "query"),
                    description=param.get("description", ""),
                    default=str(param_schema.get("default")) if "default" in param_schema else None,
                ))

            # Request body
            req_body = operation.get("requestBody", {})
            if req_body:
                content = req_body.get("content", {})
                json_content = content.get("application/json", {})
                if json_content and "schema" in json_content:
                    endpoint.request_body_type = openapi_type_to_ts(
                        json_content["schema"], spec_data
                    )
                    endpoint.request_body_required = req_body.get("required", False)

            # Response
            responses = operation.get("responses", {})
            success_response = responses.get("200") or responses.get("201") or responses.get("2XX")
            if success_response:
                content = success_response.get("content", {})
                json_content = content.get("application/json", {})
                if json_content and "schema" in json_content:
                    resp_schema = json_content["schema"]
                    endpoint.response_type = openapi_type_to_ts(resp_schema, spec_data)

                    # Detect paginated responses
                    if "$ref" in resp_schema:
                        ref_name = ref_to_name(resp_schema["$ref"])
                        ref_schema = schemas_raw.get(ref_name, {})
                        props = ref_schema.get("properties", {})
                        if "items" in props and "total" in props:
                            endpoint.response_is_paginated = True

            result.all_endpoints.append(endpoint)

            # Group by tag
            if tag not in tag_map:
                tag_map[tag] = TagGroup(tag=tag)
            tag_map[tag].endpoints.append(endpoint)

    result.tag_groups = list(tag_map.values())
    return result


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _parse_property(name: str, schema: dict, required: bool, spec: dict) -> PropertyInfo:
    ts_type = openapi_type_to_ts(schema, spec)
    nullable = "null" in ts_type if isinstance(ts_type, str) else False

    return PropertyInfo(
        name=name,
        ts_type=ts_type,
        required=required,
        description=schema.get("description", ""),
        format=schema.get("format", ""),
        is_array=schema.get("type") == "array",
        is_enum="enum" in schema,
        enum_values=schema.get("enum", []),
        nullable=nullable,
        default=str(schema["default"]) if "default" in schema else None,
    )


def _clean_operation_id(op_id: str) -> str:
    """Normalize operation IDs to camelCase function names."""
    # Remove common prefixes/suffixes FastAPI adds
    op_id = re.sub(r'_api_v\d+_', '_', op_id)
    op_id = re.sub(r'_+', '_', op_id).strip('_')

    # Convert to camelCase
    parts = op_id.split('_')
    return parts[0] + ''.join(p.capitalize() for p in parts[1:])


def _resolve_ref(ref: str, spec: dict) -> dict:
    """Resolve a $ref pointer within the spec."""
    parts = ref.lstrip("#/").split("/")
    current = spec
    for part in parts:
        current = current.get(part, {})
    return current


def load_spec(source: str) -> dict:
    """Load an OpenAPI spec from a file path or URL."""
    if source.startswith("http://") or source.startswith("https://"):
        import urllib.request
        with urllib.request.urlopen(source) as resp:
            return json.loads(resp.read())
    else:
        path = Path(source)
        text = path.read_text()
        if path.suffix in (".yaml", ".yml"):
            try:
                import yaml
                return yaml.safe_load(text)
            except ImportError:
                raise ImportError("PyYAML required for YAML specs: pip install pyyaml")
        return json.loads(text)
