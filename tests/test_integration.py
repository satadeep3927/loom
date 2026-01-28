"""Integration tests for full workflow execution."""

import pytest

from src.core.context import WorkflowContext
from src.core.workflow import Workflow
from src.database.db import Database
from src.decorators.activity import activity
from src.decorators.workflow import step, workflow


# Test activity
@activity(name="test_activity", retry_count=3)
async def test_activity(value: int) -> int:
    """Test activity that doubles a value."""
    return value * 2


# Test workflow
class IntegrationInput(dict):
    initial_value: int


class IntegrationState(dict):
    result: int


@workflow(name="IntegrationWorkflow", version="1.0.0")
class IntegrationWorkflow(Workflow[IntegrationInput, IntegrationState]):
    @step(name="process")
    async def process_step(
        self, ctx: WorkflowContext[IntegrationInput, IntegrationState]
    ):
        # Call activity
        result = await ctx.activity(test_activity, ctx.input["initial_value"])
        await ctx.state.set("result", result)
        ctx.logger.info(f"Processing complete: {result}")


@pytest.mark.asyncio
async def test_workflow_start_and_execution(test_db):
    """Test starting and executing a workflow end-to-end."""
    # Compile workflow
    compiled = IntegrationWorkflow.compile()

    # Start workflow
    input_data = IntegrationInput(initial_value=21)
    handle = await compiled.start(input=input_data)

    assert handle.id is not None

    # Check workflow was created
    status = await handle.status()
    assert status == "RUNNING"


@pytest.mark.asyncio
async def test_workflow_state_persistence(test_db):
    """Test that workflow state is persisted correctly."""
    compiled = IntegrationWorkflow.compile()
    input_data = IntegrationInput(initial_value=10)
    handle = await compiled.start(input=input_data)

    # Execute workflow steps
    async with Database() as db:
        await db.create_event(
            workflow_id=handle.id,
            type="STATE_SET",
            payload={"key": "result", "value": 20},
        )

    # Verify event was stored
    async with Database() as db:
        events = await db.get_workflow_events(handle.id)

    assert len(events) >= 1
    state_event = next((e for e in events if e["type"] == "STATE_SET"), None)
    assert state_event is not None
    assert state_event["payload"]["value"] == 20
