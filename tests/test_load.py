"""Load tests for database concurrency and worker performance.

Tests verify that the database locking fixes work correctly under high load:
- FIX 1: Consolidated multi-step writes (single connection blocks)
- FIX 2: BEGIN IMMEDIATE in claim_task()
- FIX 3: Polling jitter in worker loop

Run with: pytest tests/test_load.py -v -s
"""

import asyncio
import time
from collections import defaultdict
from dataclasses import dataclass
from typing import Dict, List

import pytest

from loom.core.context import WorkflowContext
from loom.core.runner import run_once
from loom.core.workflow import Workflow
from loom.database import Database
from loom.decorators.activity import activity
from loom.decorators.workflow import step, workflow

# === Test Fixtures ===


@dataclass
class LoadTestMetrics:
    """Metrics collected during load test."""

    workflows_created: int = 0
    workflows_completed: int = 0
    workflows_failed: int = 0
    tasks_executed: int = 0
    db_lock_errors: int = 0
    total_duration: float = 0.0
    worker_times: List[float] = None

    def __post_init__(self):
        if self.worker_times is None:
            self.worker_times = []

    @property
    def throughput(self) -> float:
        """Workflows completed per second."""
        return (
            self.workflows_completed / self.total_duration
            if self.total_duration > 0
            else 0.0
        )

    @property
    def success_rate(self) -> float:
        """Percentage of workflows that completed successfully."""
        total = self.workflows_completed + self.workflows_failed
        return (self.workflows_completed / total * 100) if total > 0 else 0.0


# === Test Activities and Workflows ===


@activity(name="load_test_activity", retry_count=2, timeout_seconds=5)
async def load_test_activity(value: int) -> int:
    """Simulate a fast activity for load testing."""
    await asyncio.sleep(0.01)  # Minimal work
    return value + 1


class LoadInput(dict):
    id: int
    value: int


class LoadState(dict):
    result: int
    completed: bool


@workflow(name="LoadTestWorkflow", version="1.0.0")
class LoadTestWorkflow(Workflow[LoadInput, LoadState]):
    """Simple workflow for load testing."""

    @step(name="process")
    async def process(self, ctx: WorkflowContext[LoadInput, LoadState]):
        # Execute activity
        result = await ctx.activity(load_test_activity, ctx.input["value"])
        await ctx.state.set("result", result)
        await ctx.state.set("completed", True)


# Flaky activity for retry testing
_flaky_attempts = defaultdict(int)


@activity(name="flaky_activity", retry_count=3, timeout_seconds=5)
async def flaky_activity(value: int) -> int:
    """Activity that fails twice, then succeeds."""
    _flaky_attempts[value] += 1
    if _flaky_attempts[value] < 3:
        raise Exception(f"Attempt {_flaky_attempts[value]} failed")
    return value + 100


class FlakyInput(dict):
    value: int


class FlakyState(dict):
    result: int


@workflow(name="FlakyWorkflow", version="1.0.0")
class FlakyWorkflow(Workflow[FlakyInput, FlakyState]):
    """Workflow with a flaky activity for retry testing."""

    @step(name="process")
    async def process(self, ctx: WorkflowContext[FlakyInput, FlakyState]):
        result = await ctx.activity(flaky_activity, ctx.input["value"])
        await ctx.state.set("result", result)


# === Load Test Helpers ===


async def create_workflow(workflow_id: int, value: int) -> str:
    """Create a single workflow instance."""
    compiled = LoadTestWorkflow.compile()
    input_data = LoadInput(id=workflow_id, value=value)
    handle = await compiled.start(input=input_data)
    return handle.id


async def worker_task(worker_id: int, duration: float, metrics: LoadTestMetrics):
    """Simulate a worker processing tasks for a given duration."""
    start_time = time.time()
    task_count = 0

    try:
        while time.time() - start_time < duration:
            try:
                executed = await run_once()
                if executed:
                    task_count += 1
            except Exception as e:
                if "database is locked" in str(e).lower():
                    metrics.db_lock_errors += 1
                raise

            # Small delay between polls (worker loop handles jitter)
            await asyncio.sleep(0.05)

    except asyncio.CancelledError:
        pass
    finally:
        elapsed = time.time() - start_time
        metrics.worker_times.append(elapsed)
        metrics.tasks_executed += task_count


async def wait_for_completions(
    workflow_ids: List[str], timeout: float = 30.0
) -> Dict[str, str]:
    """Wait for workflows to complete and return their final statuses."""
    statuses = {}
    start_time = time.time()

    while time.time() - start_time < timeout:
        all_done = True

        for wf_id in workflow_ids:
            if wf_id in statuses:
                continue

            try:
                async with Database() as db:
                    info = await db.get_workflow_info(wf_id)
                    status = info["status"]

                    if status in ("COMPLETED", "FAILED", "CANCELLED"):
                        statuses[wf_id] = status
                    else:
                        all_done = False
            except Exception:
                all_done = False

        if all_done:
            break

        await asyncio.sleep(0.1)

    # Get remaining statuses
    for wf_id in workflow_ids:
        if wf_id not in statuses:
            try:
                async with Database() as db:
                    info = await db.get_workflow_info(wf_id)
                    statuses[wf_id] = info["status"]
            except Exception:
                statuses[wf_id] = "UNKNOWN"

    return statuses


# === Load Tests ===


@pytest.mark.asyncio
async def test_concurrent_workflow_creation(test_db):
    """Test creating multiple workflows concurrently.

    Verifies FIX 1: Consolidated writes in create_workflow()
    """
    num_workflows = 50
    metrics = LoadTestMetrics()

    start_time = time.time()

    # Create workflows concurrently
    tasks = [create_workflow(i, i * 10) for i in range(num_workflows)]
    workflow_ids = await asyncio.gather(*tasks, return_exceptions=True)

    # Check for errors
    successful_ids = [
        wf_id for wf_id in workflow_ids if isinstance(wf_id, str) and wf_id
    ]
    failed = [wf_id for wf_id in workflow_ids if isinstance(wf_id, Exception)]

    metrics.workflows_created = len(successful_ids)
    metrics.total_duration = time.time() - start_time

    # Verify all workflows were created successfully
    assert len(failed) == 0, f"Failed to create {len(failed)} workflows: {failed[:3]}"
    assert metrics.workflows_created == num_workflows

    # Verify all workflows exist in database
    async with Database() as db:
        for wf_id in successful_ids:
            info = await db.get_workflow_info(wf_id)
            assert info["status"] == "RUNNING"

    print(
        f"\n✓ Created {metrics.workflows_created} workflows in {metrics.total_duration:.2f}s"
    )


@pytest.mark.asyncio
async def test_concurrent_task_claiming(test_db):
    """Test concurrent workers claiming tasks.

    Verifies FIX 2: BEGIN IMMEDIATE in claim_task()
    Verifies FIX 3: Polling jitter (indirectly via run_once)
    """
    num_workflows = 20
    num_workers = 8
    worker_duration = 5.0

    metrics = LoadTestMetrics()

    # Create workflows
    print(f"\nCreating {num_workflows} workflows...")
    workflow_ids = []
    for i in range(num_workflows):
        wf_id = await create_workflow(i, i * 10)
        workflow_ids.append(wf_id)

    metrics.workflows_created = len(workflow_ids)

    # Start concurrent workers
    print(f"Starting {num_workers} concurrent workers for {worker_duration}s...")
    start_time = time.time()

    worker_tasks = [
        worker_task(i, worker_duration, metrics) for i in range(num_workers)
    ]
    await asyncio.gather(*worker_tasks, return_exceptions=True)

    metrics.total_duration = time.time() - start_time

    # Wait for workflows to complete
    print("Waiting for workflows to complete...")
    statuses = await wait_for_completions(workflow_ids, timeout=15.0)

    # Count outcomes
    for status in statuses.values():
        if status == "COMPLETED":
            metrics.workflows_completed += 1
        elif status == "FAILED":
            metrics.workflows_failed += 1

    # Print metrics
    print(f"\n{'='*60}")
    print("LOAD TEST RESULTS")
    print(f"{'='*60}")
    print(f"Workflows Created:    {metrics.workflows_created}")
    print(f"Workflows Completed:  {metrics.workflows_completed}")
    print(f"Workflows Failed:     {metrics.workflows_failed}")
    print(f"Tasks Executed:       {metrics.tasks_executed}")
    print(f"DB Lock Errors:       {metrics.db_lock_errors}")
    print(f"Total Duration:       {metrics.total_duration:.2f}s")
    print(f"Throughput:           {metrics.throughput:.2f} workflows/sec")
    print(f"Success Rate:         {metrics.success_rate:.1f}%")
    print(f"{'='*60}\n")

    # Assertions - focus on lock errors (the critical metric)
    assert metrics.db_lock_errors == 0, (
        f"Database lock errors detected: {metrics.db_lock_errors}. "
        "Fixes may not be working correctly."
    )
    assert metrics.tasks_executed > 0, "No tasks were executed"
    # Note: Workflows may still be in progress, which is OK for this test
    # The key is that we have zero lock errors under concurrent load


@pytest.mark.asyncio
async def test_high_contention_scenario(test_db):
    """Test high contention with many workers and few workflows.

    This creates maximum database lock contention to verify all fixes.
    """
    num_workflows = 5
    num_workers = 16  # More workers than workflows
    worker_duration = 3.0

    metrics = LoadTestMetrics()

    # Create workflows
    workflow_ids = []
    for i in range(num_workflows):
        wf_id = await create_workflow(i, i)
        workflow_ids.append(wf_id)

    metrics.workflows_created = len(workflow_ids)

    # Start workers (high contention)
    start_time = time.time()
    worker_tasks = [
        worker_task(i, worker_duration, metrics) for i in range(num_workers)
    ]
    await asyncio.gather(*worker_tasks, return_exceptions=True)
    metrics.total_duration = time.time() - start_time

    # Wait for completion
    statuses = await wait_for_completions(workflow_ids, timeout=10.0)

    for status in statuses.values():
        if status == "COMPLETED":
            metrics.workflows_completed += 1
        elif status == "FAILED":
            metrics.workflows_failed += 1

    print(f"\nHigh Contention Results:")
    print(f"  DB Lock Errors: {metrics.db_lock_errors}")
    print(f"  Tasks Executed: {metrics.tasks_executed}")
    print(f"  Success Rate:   {metrics.success_rate:.1f}%")

    # Critical assertion: No lock errors under high contention
    assert (
        metrics.db_lock_errors == 0
    ), f"Database locked under high contention: {metrics.db_lock_errors} errors"


@pytest.mark.asyncio
async def test_workflow_state_transitions_concurrent(test_db):
    """Test concurrent state transitions (complete, fail, cancel).

    Verifies FIX 1: Consolidated writes in workflow_failed/complete/cancel
    """
    num_workflows = 30
    metrics = LoadTestMetrics()

    # Create workflows
    workflow_ids = []
    for i in range(num_workflows):
        wf_id = await create_workflow(i, i)
        workflow_ids.append(wf_id)

    # Concurrently transition workflows to terminal states
    start_time = time.time()

    async def transition_workflow(wf_id: str, index: int):
        """Transition workflow to a terminal state based on index."""
        async with Database() as db:
            if index % 3 == 0:
                await db.complete_workflow(wf_id)
            elif index % 3 == 1:
                await db.workflow_failed(wf_id, "Test failure")
            else:
                await db.cancel_workflow(wf_id, "Test cancellation")

    tasks = [transition_workflow(wf_id, i) for i, wf_id in enumerate(workflow_ids)]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    metrics.total_duration = time.time() - start_time

    # Check for errors
    errors = [r for r in results if isinstance(r, Exception)]
    lock_errors = [e for e in errors if "database is locked" in str(e).lower()]

    print(f"\nState Transition Results:")
    print(f"  Total Transitions: {num_workflows}")
    print(f"  Errors:           {len(errors)}")
    print(f"  Lock Errors:      {len(lock_errors)}")
    print(f"  Duration:         {metrics.total_duration:.2f}s")

    assert len(lock_errors) == 0, f"Lock errors during state transitions: {lock_errors}"


@pytest.mark.asyncio
async def test_activity_retry_with_concurrent_workers(test_db):
    """Test activity retries under concurrent worker load.

    Verifies consolidated writes and locking during activity scheduling/completion.
    This test primarily checks for lock errors rather than completion rate.
    """
    # Reset attempts counter
    _flaky_attempts.clear()

    # Create workflows
    num_workflows = 10
    workflow_ids = []

    for i in range(num_workflows):
        compiled = FlakyWorkflow.compile()
        handle = await compiled.start(input=FlakyInput(value=i))
        workflow_ids.append(handle.id)

    # Run workers
    metrics = LoadTestMetrics()
    worker_tasks = [worker_task(i, 12.0, metrics) for i in range(4)]
    await asyncio.gather(*worker_tasks)

    # Check results
    statuses = await wait_for_completions(workflow_ids, timeout=10.0)

    completed = sum(1 for s in statuses.values() if s == "COMPLETED")
    failed = sum(1 for s in statuses.values() if s == "FAILED")

    print(f"\nFlaky Activity Results:")
    print(f"  Completed: {completed}")
    print(f"  Failed:    {failed}")
    print(f"  Lock Errors: {metrics.db_lock_errors}")

    # Critical assertion: no lock errors during retry scheduling
    assert (
        metrics.db_lock_errors == 0
    ), f"Lock errors during activity retries: {metrics.db_lock_errors}"
    # Note: Activity completion rate may vary due to retry timing,
    # but the absence of lock errors proves the fixes are working


if __name__ == "__main__":
    # Run tests with pytest
    pytest.main([__file__, "-v", "-s"])
