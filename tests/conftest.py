"""Test configuration and fixtures."""

import asyncio
import os
import tempfile

import pytest

from src.common.config import DATABASE
from src.database.db import Database


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def test_db():
    """Provide a clean test database for each test."""
    # Create temporary database
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        tmp_path = tmp.name

    # Override database path
    original_db = DATABASE
    import src.common.config as config

    config.DATABASE = tmp_path

    # Initialize database
    db = Database()
    await db._init_db()

    yield db

    # Cleanup
    config.DATABASE = original_db
    try:
        os.unlink(tmp_path)
    except Exception:
        pass


@pytest.fixture
def sample_workflow_input():
    """Sample workflow input data."""
    return {"message": "test input"}


@pytest.fixture
def sample_workflow_state():
    """Sample workflow state data."""
    return {"count": 0, "processed": False}
