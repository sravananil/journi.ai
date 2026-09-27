"""
conftest.py — shared pytest fixtures
=====================================
Uses the DATABASE_URL from the environment (.env).
Tests run inside a rolled-back transaction to prevent data mutation.
"""

import os
import pytest
from dotenv import load_dotenv

load_dotenv()

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.db.database import Base

# Use a test-specific database if TEST_DATABASE_URL is set, otherwise use the main one.
# Tests use transaction rollback — they never permanently modify the database.
TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL", os.getenv("DATABASE_URL", "sqlite:///./journi.db"))


@pytest.fixture(scope="session")
def test_engine():
    """Create a single engine for the entire test session."""
    engine = create_engine(TEST_DATABASE_URL, pool_pre_ping=True)
    yield engine
    engine.dispose()


@pytest.fixture(scope="function")
def db(test_engine):
    """
    Provide a database session that is rolled back after each test.
    This ensures tests do not modify the real database.
    """
    connection = test_engine.connect()
    transaction = connection.begin()
    Session = sessionmaker(bind=connection)
    session = Session()
    
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()
