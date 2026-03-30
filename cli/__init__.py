#!/usr/bin/env python3
"""
⚡ FastForge CLI
==================

Workflow:
  1. fastforge init my-app           — scaffold project (FastAPI backend)
  1b. fastforge init my-app --react  — scaffold with React frontend too
  2. fastforge crud product           — create model stub (you edit it)
  3. fastforge migrate                — create DB migration from model
  4. fastforge generate product       — generate schemas, repo, service, router FROM model
  5. fastforge add-frontend           — add React frontend to existing project
  6. fastforge generate-client        — sync frontend TypeScript from OpenAPI

The MODEL is the single source of truth.
"""
import argparse
import sys
import os
import json
from pathlib import Path

FRAMEWORK_VERSION = "0.3.0"
CONFIG_FILE = "fastforge.json"


def _load_config() -> tuple[dict, Path | None]:
    """Load config and return (config, config_dir).

    Paths in the config are relative to the config file's directory,
    so callers must resolve them using config_dir.
    """
    for search in [Path("."), *Path(".").resolve().parents]:
        cfg = search / CONFIG_FILE
        if cfg.exists():
            with open(cfg) as f:
                return json.load(f), cfg.parent.resolve()
    return {}, None


def _resolve_path(config: dict, key: str, config_dir: Path | None) -> str:
    """Resolve a path from config relative to the config file's directory."""
    raw = config.get("paths", {}).get(key, key)
    if config_dir is None:
        return raw
    return str(config_dir / raw)


def _save_config(config: dict):
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)


def main():
    parser = argparse.ArgumentParser(
        prog="fastforge",
        description="⚡ FastForge — Full-stack framework for React + FastAPI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Workflow:
  fastforge init my-app                    Create project (FastAPI only)
  fastforge init my-app --react            Create project with React frontend
  fastforge crud product                   Create model stub → edit it
  fastforge migrate                        Create DB migration
  fastforge generate product               Generate schemas/repo/service/router from model
  fastforge generate --all                 Generate for ALL models
  fastforge add-frontend                   Add React frontend to existing project
  fastforge generate-client -i <url>       Sync frontend TypeScript from OpenAPI

Examples:
  fastforge init my-app
  fastforge init my-app --react
  fastforge crud product
  fastforge generate product
  fastforge generate --all
  fastforge add-frontend
  fastforge generate-client -i http://localhost:8000/api/v1/openapi.json
        """,
    )
    parser.add_argument("--version", action="version", version=f"fastforge {FRAMEWORK_VERSION}")
    sub = parser.add_subparsers(dest="command")

    # ── init ─────────────────────────────────────────────────────────────
    p = sub.add_parser("init", help="Scaffold a new project (FastAPI backend)")
    p.add_argument("name", help="Project name")
    p.add_argument("--db", default="postgres", choices=["postgres", "sqlite", "mysql", "mongodb"])
    p.add_argument("--react", action="store_true", help="Include React frontend")

    # ── crud ─────────────────────────────────────────────────────────────
    p = sub.add_parser("crud", help="Create a model stub (step 1)")
    p.add_argument("entity", help="Entity name (e.g., product)")

    # ── migrate ──────────────────────────────────────────────────────────
    p = sub.add_parser("migrate", help="Create DB migration from models (step 2)")
    p.add_argument("--message", "-m", default=None, help="Migration message")

    # ── generate ─────────────────────────────────────────────────────────
    p = sub.add_parser("generate", help="Generate schemas/repo/service/router from model (step 3)")
    p.add_argument("entity", nargs="?", help="Entity name (reads model file)")
    p.add_argument("--all", action="store_true", help="Generate for ALL models")
    p.add_argument("--force", action="store_true", help="Overwrite service and router (loses custom code)")

    # ── generate-client ──────────────────────────────────────────────────
    p = sub.add_parser("generate-client", help="Sync frontend TypeScript from OpenAPI")
    p.add_argument("-i", "--input", required=True, help="OpenAPI spec URL or file path")
    p.add_argument("-o", "--output", default="src/api", help="Output directory")
    p.add_argument("--skip-auth", action="store_true")

    # ── add-frontend ──────────────────────────────────────────────────────
    sub.add_parser("add-frontend", help="Add React frontend to existing project")

    # ── list ─────────────────────────────────────────────────────────────
    sub.add_parser("list", help="List all models")

    args = parser.parse_args()

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    if args.command == "init":
        from .cmd_init import run_init
        run_init(args.name, db=args.db, with_react=args.react)

    # ── add-frontend ─────────────────────────────────────────────────────
    elif args.command == "add-frontend":
        from .cmd_init import add_frontend
        config, config_dir = _load_config()
        if not config:
            print("❌ No fastforge.json found. Run: fastforge init <name>")
            sys.exit(1)
        if config.get("paths", {}).get("frontend"):
            fe_path = _resolve_path(config, "frontend", config_dir)
            if os.path.exists(fe_path):
                print(f"❌ Frontend already exists: {fe_path}")
                sys.exit(1)
        add_frontend(config, config_dir)

    # ── crud: create model stub only ─────────────────────────────────────
    elif args.command == "crud":
        from .gen_model_stub import generate_model_stub, register_model_imports
        from .field_mappings import to_snake, to_pascal

        config, config_dir = _load_config()
        be_path = _resolve_path(config, "backend", config_dir)
        snake = to_snake(args.entity)
        pascal = to_pascal(args.entity)

        print(f"\n⚡ FastForge — Creating model: {pascal}\n")
        model_path = generate_model_stub(args.entity, be_path)

        # Auto-register imports in main.py and migrations/env.py
        register_model_imports(args.entity, be_path)
        print(f"  ✅ Registered {pascal} import in main.py and migrations/env.py")

        print(f"\n{'─' * 60}")
        print(f"  Next steps:")
        print(f"    1. Edit the model:  {model_path}")
        print(f"    2. Run migration:   fastforge migrate")
        print(f"    3. Generate code:   fastforge generate {snake}")
        print(f"{'─' * 60}\n")

    # ── migrate: create alembic migration ────────────────────────────────
    elif args.command == "migrate":
        from .field_mappings import to_snake
        config, config_dir = _load_config()
        be_path = _resolve_path(config, "backend", config_dir)

        message = args.message or "auto migration"
        print(f"\n⚡ FastForge — Creating migration: {message}\n")

        from fastforge_core.db.alembic_utils import init_alembic, generate_migration, run_migrations, run_seeders
        init_alembic(be_path)
        if generate_migration(be_path, message):
            print("\n  Applying migration...")
            run_migrations(be_path, "up")
            print("\n  Running seeders...")
            run_seeders(be_path)

    # ── generate: read model → generate everything else ──────────────────
    elif args.command == "generate":
        from .gen_from_model import generate_from_model
        from .model_introspector import introspect_models_dir
        from .field_mappings import to_snake

        config, config_dir = _load_config()
        be_path = _resolve_path(config, "backend", config_dir)
        models_dir = f"{be_path}/app/models"

        if args.all:
            # Generate for ALL models
            from .model_introspector import introspect_models_dir
            models = introspect_models_dir(models_dir)
            if not models:
                print("❌ No models found in", models_dir)
                sys.exit(1)

            print(f"\n⚡ FastForge — Generating from {len(models)} model(s)\n")
            for m in models:
                print(f"{'─' * 60}")
                generate_from_model(m.file_path, be_path, force=args.force)
            print(f"\n✅ All done! Start server and run:")
            print(f"   fastforge generate-client -i http://localhost:8000/api/v1/openapi.json\n")

        elif args.entity:
            snake = to_snake(args.entity)
            model_path = f"{models_dir}/{snake}.py"

            if not os.path.exists(model_path):
                print(f"❌ Model not found: {model_path}")
                print(f"   Run first: fastforge crud {args.entity}")
                sys.exit(1)

            print(f"\n⚡ FastForge — Generating from model: {model_path}")
            generate_from_model(model_path, be_path, force=args.force)

            print(f"\n✅ Done! Start server and run:")
            print(f"   fastforge generate-client -i http://localhost:8000/api/v1/openapi.json\n")

        else:
            print("❌ Specify an entity name or use --all")
            print("   fastforge generate product")
            print("   fastforge generate --all")
            sys.exit(1)

    # ── generate-client ──────────────────────────────────────────────────
    elif args.command == "generate-client":
        from .generate_client import run_generate_client
        success = run_generate_client(
            input_source=args.input,
            output_dir=args.output,
            skip_auth=args.skip_auth,
        )
        sys.exit(0 if success else 1)

    # ── list ─────────────────────────────────────────────────────────────
    elif args.command == "list":
        from .model_introspector import introspect_models_dir
        config, config_dir = _load_config()
        be_path = _resolve_path(config, "backend", config_dir)
        models_dir = f"{be_path}/app/models"

        models = introspect_models_dir(models_dir)
        if not models:
            print("\n📋 No models found. Run: fastforge crud <entity>")
            return

        print(f"\n📋 Models ({len(models)}):\n")
        for m in models:
            cols = ", ".join(f"{c.name}:{c.python_type}{'?' if c.nullable else ''}" for c in m.user_columns)
            print(f"  • {m.class_name} ({m.base_class}) → {cols}")

            # Check what's generated
            checks = {
                "schema": f"{be_path}/app/schemas/{_to_snake(m.class_name)}.py",
                "repo": f"{be_path}/app/repositories/{_to_snake(m.class_name)}_repository.py",
                "service": f"{be_path}/app/services/{_to_snake(m.class_name)}_service.py",
                "router": f"{be_path}/app/api/routes/{_to_snake(m.class_name)}.py",
            }
            existing = [k for k, v in checks.items() if os.path.exists(v)]
            missing = [k for k, v in checks.items() if not os.path.exists(v)]

            if missing:
                print(f"    ⚠ Missing: {', '.join(missing)} → run: fastforge generate {_to_snake(m.class_name)}")
            else:
                print(f"    ✅ All generated")
        print()

    elif args.command is None:
        parser.print_help()
    else:
        print(f"❌ Unknown command: {args.command}")
        sys.exit(1)


def _to_snake(name):
    import re
    s = re.sub(r'(.)([A-Z][a-z]+)', r'\1_\2', name)
    return re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', s).lower()


if __name__ == "__main__":
    main()
