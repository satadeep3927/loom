"""Tests for activity decorator and execution."""

import pytest

from src.decorators.activity import activity


def test_activity_decorator_basic():
    """Test basic activity decoration."""

    @activity(name="test_activity")
    async def my_activity():
        return "result"

    assert hasattr(my_activity, "_activity_name")
    assert my_activity._activity_name == "test_activity"


def test_activity_decorator_with_options():
    """Test activity decorator with all options."""

    @activity(
        name="complex_activity",
        description="Does complex things",
        retry_count=5,
        timeout_seconds=120,
    )
    async def my_activity(param: str):
        return f"processed: {param}"

    assert my_activity._activity_name == "complex_activity"
    assert my_activity._activity_description == "Does complex things"
    assert my_activity._activity_retry_count == 5
    assert my_activity._activity_timeout_seconds == 120


def test_activity_defaults():
    """Test that activity decorator uses sensible defaults."""

    @activity()
    async def my_activity():
        pass

    assert my_activity._activity_name == "my_activity"
    assert my_activity._activity_description == ""
    assert my_activity._activity_retry_count == 0
    assert my_activity._activity_timeout_seconds == 60


def test_activity_retry_count_validation():
    """Test that negative retry_count raises ValueError."""
    with pytest.raises(ValueError, match="non-negative integer"):

        @activity(retry_count=-1)
        async def my_activity():
            pass


def test_activity_timeout_validation():
    """Test that invalid timeout raises ValueError."""
    with pytest.raises(ValueError, match="positive integer"):

        @activity(timeout_seconds=0)
        async def my_activity():
            pass


def test_activity_excessive_retry_validation():
    """Test that excessive retry_count raises ValueError."""
    with pytest.raises(ValueError, match="excessive"):

        @activity(retry_count=101)
        async def my_activity():
            pass


def test_activity_excessive_timeout_validation():
    """Test that excessive timeout raises ValueError."""
    with pytest.raises(ValueError, match="excessive"):

        @activity(timeout_seconds=3601)
        async def my_activity():
            pass


@pytest.mark.asyncio
async def test_activity_execution():
    """Test that decorated activity can be executed."""

    @activity(name="executable_activity")
    async def my_activity(x: int, y: int):
        return x + y

    result = await my_activity(2, 3)
    assert result == 5
