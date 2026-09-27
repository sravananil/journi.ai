"""
Alembic env.py — JOURNI Migration Environment
Reads DATABASE_URL from environment via python-dotenv.
Never hardcodes credentials.
"""

import os
import sys
from logging.config import fileConfig
from dotenv import load_dotenv

# Add backend root to path so models can be imported
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load environment variables from .env before anything else
load_dotenv()

from sqlalchemy import engine_from_config
from sqlalchemy import pool
from alembic import context

# ─── Alembic Config ───────────────────────────────────────────────────────────

config = context.config

# Override sqlalchemy.url from environment (never from alembic.ini credentials)
database_url = os.environ.get("DATABASE_URL")
if not database_url:
    raise RuntimeError(
        "DATABASE_URL environment variable is not set. "
        "Create a backend/.env file with DATABASE_URL=postgresql+psycopg2://..."
    )
config.set_main_option("sqlalchemy.url", database_url)

# Interpret the config file for Python logging setup
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Import ALL models so Alembic can auto-detect them
from app.db.database import Base
import app.models.city          # noqa: F401
import app.models.destination   # noqa: F401
import app.models.place         # noqa: F401
import app.models.restaurant    # noqa: F401

target_metadata = Base.metadata


# ─── Migration Runners ────────────────────────────────────────────────────────

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (generates SQL script without connecting)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode (connects and applies changes)."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
