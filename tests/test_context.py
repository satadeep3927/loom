"""Tests for workflow context and state management."""

import pytest

from src.common.errors import StopReplay
from src.core.context import WorkflowContext
from src.schemas.events import Event


class TestInput(dict):
    message: str


class TestState(dict):
    count: int
    processed: bool


@pytest.mark.asyncio
async def test_context_initialization():
    """Test WorkflowContext initialization."""
    input_data = TestInput(message="test")
    state_data = TestState(count=0, processed=False)
    history: list[Event] = []

    ctx = WorkflowContext(
        id="test-workflow-123",
        input=input_data,
        history=history,
        state=state_data,
    )

    assert ctx.id == "test-workflow-123"
    assert ctx.input["message"] == "test"
    assert ctx.cursor == 0
    assert not ctx.is_replaying


@pytest.mark.asyncio
async def test_state_proxy_set():
    """Test state proxy set operation."""
    input_data = TestInput(message="test")
    state_data = TestState(count=0)
    history: list[Event] = []

    ctx = WorkflowContext(
        id="test-workflow",
        input=input_data,
        history=history,
        state=state_data,
    )

    with pytest.raises(StopReplay):
        await ctx.state.set("count", 42)
    assert ctx.state.get("count") == 42


@pytest.mark.asyncio
async def test_state_proxy_update():
    """Test state proxy update operation."""
    input_data = TestInput(message="test")
    state_data = TestState(count=0, processed=False)
    history: list[Event] = []

    ctx = WorkflowContext(
        id="test-workflow",
        input=input_data,
        history=history,
        state=state_data,
    )

    # Update multiple values using async functions
    async def update_count(_):
        return 10

    async def update_processed(_):
        return True

    with pytest.raises(StopReplay):
        await ctx.state.update(count=update_count, processed=update_processed)


def test_event_replay():
    """Test event history replay."""
    input_data = TestInput(message="test")
    state_data = TestState(count=0)
    history: list[Event] = [
        Event(type="WORKFLOW_STARTED", payload={}),
        Event(type="STATE_SET", payload={"key": "count", "value": 5}),
        Event(type="STATE_SET", payload={"key": "processed", "value": True}),
    ]

    ctx = WorkflowContext(
        id="test-workflow",
        input=input_data,
        history=history,
        state=state_data,
    )

    # Context should be in replay mode
    assert ctx.is_replaying
    assert len(ctx.history) == 3

    # Peek at first event
    event = ctx._peek()
    assert event is not None
    assert event["type"] == "WORKFLOW_STARTED"

    # Consume first event
    consumed = ctx._consume()
    assert consumed["type"] == "WORKFLOW_STARTED"
    assert ctx.cursor == 1


def test_match_event():
    """Test event matching during replay."""
    input_data = TestInput(message="test")
    state_data = TestState()
    history: list[Event] = [
        Event(type="ACTIVITY_SCHEDULED", payload={"name": "test_activity"}),
        Event(type="ACTIVITY_COMPLETED", payload={"result": "success"}),
    ]

    ctx = WorkflowContext(
        id="test-workflow",
        input=input_data,
        history=history,
        state=state_data,
    )

    # Match should find the activity scheduled event
    matched = ctx._match_event("ACTIVITY_SCHEDULED")
    assert matched is not None
    assert matched["type"] == "ACTIVITY_SCHEDULED"

    # Non-matching type should return None
    not_matched = ctx._match_event("WORKFLOW_COMPLETED")
    assert not_matched is None
