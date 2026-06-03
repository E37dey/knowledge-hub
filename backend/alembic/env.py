"""Alembic environment.

Wired to read the database URL from `app.config.settings` (which loads
.env via pydantic-settings) instead of from alembic.ini, so the
connection string is never committed.

Also imports `app.models` so every ORM class registers itself on
`Base.metadata` — that's what `--autogenerate` diffs against.
"""
import sys
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import engine_from_config, pool

from alembic import context

# Make backend/ importable regardless of where alembic is invoked from.
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config import settings  # noqa: E402
from app.database import Base  # noqa: E402
from app import models  # noqa: F401, E402  -- registers models on Base.metadata

config = context.config

# Inject the runtime DATABASE_URL so alembic.ini stays password-free.
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Generate SQL without a live connection (for review / CI)."""
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Apply migrations with a live connection (the normal case)."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
