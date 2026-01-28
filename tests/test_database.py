"""Unit tests for database operations."""

import pytest

from loom.database.db import Database


@pytest.mark.asyncio
async def test_database_initialization(test_db):
    """Test that database initializes correctly."""
    async with Database() as db:
        # Database should be accessible
        result = await db.query("SELECT 1 as test")
        assert len(list(result)) == 1


@pytest.mark.asyncio
async def test_create_workflow(test_db):
    """Test workflow creation."""
    async with Database() as db:
        workflow_data = {
            "name": "TestWorkflow",
            "description": "Test description",
            "version": "1.0.0",
            "status": "RUNNING",
            "module": "test.module",
            "steps": [],
        }
        input_data = {"test": "input"}

        workflow_id = await db.create_workflow(workflow_data, input_data)  # type: ignore

        assert workflow_id is not None

        # Verify workflow was created
        workflow = await db.get_workflow_info(workflow_id)
        assert workflow["name"] == "TestWorkflow"
        assert workflow["status"] == "RUNNING"


@pytest.mark.asyncio
async def test_create_and_retrieve_events(test_db):
    """Test event creation and retrieval."""
    async with Database() as db:
        # Create a workflow first
        workflow_data = {
            "name": "EventTestWorkflow",
            "description": "",
            "version": "1.0.0",
            "status": "RUNNING",
            "module": "test",
            "steps": [],
        }
        workflow_id = await db.create_workflow(workflow_data, {})  # type: ignore

        # Create events
        await db.create_event(workflow_id, "STATE_SET", {"key": "count", "value": 1})
        await db.create_event(workflow_id, "STATE_SET", {"key": "count", "value": 2})

        # Retrieve events
        events = await db.get_workflow_events(workflow_id)

        assert len(events) >= 3  # WORKFLOW_STARTED + 2 STATE_SET
        state_events = [e for e in events if e["type"] == "STATE_SET"]
        assert len(state_events) == 2


@pytest.mark.asyncio
async def test_workflow_status(test_db):
    """Test getting workflow status."""
    async with Database() as db:
        workflow_data = {
            "name": "StatusTest",
            "description": "",
            "version": "1.0.0",
            "status": "RUNNING",
            "module": "test",
            "steps": [],
        }
        workflow_id = await db.create_workflow(workflow_data, {})  # type: ignore

        status = await db.get_workflow_status(workflow_id)
        assert status == "RUNNING"


@pytest.mark.asyncio
async def test_task_creation_and_claiming(test_db):
    """Test task queue operations."""
    async with Database() as db:
        # Create a workflow
        workflow_data = {
            "name": "TaskTest",
            "description": "",
            "version": "1.0.0",
            "status": "RUNNING",
            "module": "test",
            "steps": [],
        }
        workflow_id = await db.create_workflow(workflow_data, {})  # type: ignore

        # Workflow creation should have created a STEP task
        task = await db.claim_task()

        assert task is not None
        assert task["workflow_id"] == workflow_id
        assert task["kind"] == "STEP"
        assert task["status"] == "CLAIMED"
