"""Alembic environment for the per-user DBs.

This env is invoked once per user DB; the calling code passes the
target URL through `config.attributes["target_url"]` (or the standard
`-x url=...`) so the same script applies cleanly to each file.
"""
from __future__ import annotations

from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from backend.app.db.base import UserBase
from backend.app.db.models import user  # noqa: F401  (register tables)

config = context.config

if config.config_file_name is not None:
    try:
        fileConfig(config.config_file_name)
    except Exception:
        pass

target_metadata = UserBase.metadata


def _sync_url() -> str:
    attr_url = config.attributes.get("target_url") if hasattr(config, "attributes") else None
    x_args = context.get_x_argument(as_dictionary=True)
    url = attr_url or x_args.get("url") or config.get_main_option("sqlalchemy.url")
    if not url:
        raise RuntimeError("user-DB migration requires target_url")
    return url.replace("+aiosqlite", "").replace("+asyncpg", "+psycopg")


def run_migrations_offline() -> None:
    context.configure(
        url=_sync_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    section = config.get_section(config.config_ini_section) or {}
    section["sqlalchemy.url"] = _sync_url()
    connectable = engine_from_config(
        section, prefix="sqlalchemy.", poolclass=pool.NullPool
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
