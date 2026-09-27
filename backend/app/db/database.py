"""
JOURNI Database Configuration
==============================
Reads DATABASE_URL from the environment (loaded via python-dotenv in app/main.py).

Supported databases:
  - PostgreSQL (production/development):  postgresql+psycopg2://user:pass@host:port/db
  - SQLite (local testing only):          sqlite:///./journi.db

The application will fail at startup with a clear error if the database is unreachable.
"""

import os
import logging
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.exc import OperationalError

logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./journi.db")

# Build engine kwargs based on DB type
_is_sqlite = DATABASE_URL.startswith("sqlite")

_engine_kwargs = {}
if _is_sqlite:
    _engine_kwargs["connect_args"] = {"check_same_thread": False}
    logger.warning(
        "Using SQLite database. This is for local testing only. "
        "Set DATABASE_URL to a PostgreSQL URL for production use."
    )
else:
    # PostgreSQL connection pool settings appropriate for a small service
    _engine_kwargs["pool_size"] = 5
    _engine_kwargs["max_overflow"] = 10
    _engine_kwargs["pool_pre_ping"] = True  # Detect stale connections automatically

engine = create_engine(DATABASE_URL, **_engine_kwargs)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """FastAPI dependency: yields a database session and ensures cleanup."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_db_connection() -> tuple[bool, str]:
    """
    Verify that the database is reachable.
    Returns (is_healthy: bool, message: str).
    Never exposes credentials in the message.
    """
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        db_type = "SQLite" if _is_sqlite else "PostgreSQL"
        return True, f"{db_type} connection healthy"
    except OperationalError as e:
        db_type = "SQLite" if _is_sqlite else "PostgreSQL"
        # Sanitize error: do NOT include the full DSN or credentials
        return False, f"{db_type} connection failed — check DATABASE_URL and server availability"


def create_all_tables():
    """Create all tables from SQLAlchemy metadata. Safe to call on startup."""
    Base.metadata.create_all(bind=engine)
