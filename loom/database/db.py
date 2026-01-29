import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, Generic, Iterable, List
from uuid import uuid4

import aiosqlite

from ..common.config import DATA_ROOT, DATABASE
from ..common.errors import WorkflowNotFoundError
from ..lib.utils import get_downgrade_migrations, get_upgrade_migrations
from ..schemas.activity import ActivityMetadata
from ..schemas.database import WorkflowInput
from ..schemas.events import Event
from ..schemas.tasks import Task
from ..schemas.workflow import InputT, StateT


class Database(Generic[InputT, StateT]):
    """Async SQLite database interface for workflow orchestration.

    This class provides a comprehensive interface for managing workflow data,
    including workflow instances, events, and tasks. It supports ACID transactions
    and maintains data consistency for the Loom workflow orchestration system.

    Type Parameters:
        InputT: The input type for workflows
        StateT: The state type for workflows
    """

    def __init__(self) -> None:
        """Initialize the database with migration scripts."""
        self.upgrade_migrations = get_upgrade_migrations()
        self.downgrade_migrations = get_downgrade_migrations()

    async def _init_db(self) -> None:
        """Initialize the database by creating directories and running migrations.

        Creates the data directory if it doesn't exist and applies all upgrade
        migrations to set up the database schema.
        """
        # Ensure data directory exists
        if not os.path.exists(DATA_ROOT):
            os.makedirs(DATA_ROOT, exist_ok=True)

        # Create and migrate database if it doesn't exist
        if not os.path.exists(DATABASE):
            async with aiosqlite.connect(DATABASE) as conn:
                for migration in self.upgrade_migrations:
                    await conn.executescript(migration["sql"])
                await conn.commit()

    async def query(self, sql: str, params: tuple = ()) -> Iterable[aiosqlite.Row]:
        """Execute a SELECT query and return all results.

        Args:
            sql: The SQL query string
            params: Query parameters as a tuple

        Returns:
            List of Row objects containing query results
        """
        async with aiosqlite.connect(DATABASE) as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(sql, params)
            results = await cursor.fetchall()
        return results

    async def fetchone(self, sql: str, params: tuple = ()) -> aiosqlite.Row | None:
        """Execute a SELECT query and return the first result.

        Args:
            sql: The SQL query string
            params: Query parameters as a tuple

        Returns:
            First Row object or None if no results
        """
        async with aiosqlite.connect(DATABASE) as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(sql, params)
            result = await cursor.fetchone()
            await conn.commit()
        return result

    async def execute(self, sql: str, params: tuple = ()) -> None:
        """Execute a SQL statement (INSERT, UPDATE, DELETE).

        Args:
            sql: The SQL statement string
            params: Statement parameters as a tuple
        """
        async with aiosqlite.connect(DATABASE) as conn:
            conn.row_factory = aiosqlite.Row
            await conn.execute(sql, params)
            await conn.commit()

    async def get_workflow_events(self, workflow_id: str) -> List[Event]:
        """Retrieve all events for a specific workflow in chronological order.

        Args:
            workflow_id: Unique identifier of the workflow

        Returns:
            List of Event objects ordered by creation time
        """
        sql = """
            SELECT type, payload
            FROM events
            WHERE workflow_id = ?
            ORDER BY id ASC
        """

        async with aiosqlite.connect(DATABASE) as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(sql, (workflow_id,))
            rows = await cursor.fetchall()

            events: List[Event] = []
            for row in rows:
                events.append(
                    Event(
                        type=row["type"],
                        payload=json.loads(row["payload"]),
                    )
                )
            return events

    async def get_workflow_info(self, workflow_id: str) -> Dict[str, Any]:
        """Retrieve complete information for a specific workflow.

        Args:
            workflow_id: Unique identifier of the workflow

        Returns:
            Dictionary containing workflow information

        Raises:
            WorkflowNotFoundError: If the workflow doesn't exist
        """
        sql = """
            SELECT *
            FROM workflows
            WHERE id = ?
        """

        async with aiosqlite.connect(DATABASE) as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(sql, (workflow_id,))
            row = await cursor.fetchone()

            if row:
                return {
                    "id": row["id"],
                    "name": row["name"],
                    "status": row["status"],
                    "version": row["version"],
                    "module": row["module"],
                    "input": row["input"],
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                }

            raise WorkflowNotFoundError(f"Workflow with ID {workflow_id} not found.")

    async def get_workflow_status(self, workflow_id: str) -> str:
        """Retrieve only the status of a specific workflow (optimized query).

        This is a performance-optimized version of get_workflow_info when
        only the status is needed.

        Args:
            workflow_id: Unique identifier of the workflow

        Returns:
            Workflow status string

        Raises:
            WorkflowNotFoundError: If the workflow doesn't exist
        """
        sql = """
            SELECT status
            FROM workflows
            WHERE id = ?
        """

        async with aiosqlite.connect(DATABASE) as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(sql, (workflow_id,))
            row = await cursor.fetchone()

            if row:
                return row["status"]  # type: ignore

            raise WorkflowNotFoundError(f"Workflow with ID {workflow_id} not found.")

    # === Workflow Management Methods ===
    async def recreate_workflow_task(self, workflow_id: str) -> None:
        """Recreate the initial task for a workflow.

        This method is useful for restarting or retrying a workflow by
        recreating its initial task.

        Args:
            workflow_id: Unique identifier of the workflow
        """
        task_id = self._create_id()

        workflow = await self.get_workflow_info(workflow_id)

        # Schedule first step
        task_sql = """
            INSERT INTO tasks (id, workflow_id, kind, target, run_at, status)
            VALUES (?, ?, 'STEP', ?, CURRENT_TIMESTAMP, 'PENDING')
        """
        task_params = (
            task_id,
            workflow_id,
            workflow["name"],
        )
        await self.execute(task_sql, task_params)

    async def create_workflow(self, workflow: WorkflowInput, input: InputT) -> str:
        """Create a new workflow instance with initial state.

        Creates the workflow record, adds a WORKFLOW_STARTED event, and schedules
        the first step for execution.

        Args:
            workflow: Workflow metadata and definition
            input: Input data for the workflow

        Returns:
            Unique workflow identifier
        """
        workflow_id = self._create_id()
        task_id = self._create_id()

        # Create workflow record
        workflow_sql = """
            INSERT INTO workflows (id, name, description, version, status, module, input)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        workflow_params = (
            workflow_id,
            workflow["name"],
            workflow["description"],
            workflow["version"],
            workflow["status"],
            workflow["module"],
            json.dumps(input),
        )
        await self.execute(workflow_sql, workflow_params)

        # Add workflow started event
        event_sql = """
            INSERT INTO events (workflow_id, type, payload)
            VALUES (?, 'WORKFLOW_STARTED', ?)
        """
        event_params = (
            workflow_id,
            json.dumps({"input": input}),
        )
        await self.execute(event_sql, event_params)

        # Schedule first step
        task_sql = """
            INSERT INTO tasks (id, workflow_id, kind, target, run_at, status)
            VALUES (?, ?, 'STEP', ?, CURRENT_TIMESTAMP, 'PENDING')
        """
        task_params = (
            task_id,
            workflow_id,
            workflow["name"],
        )
        await self.execute(task_sql, task_params)

        return workflow_id

    async def create_event(
        self, workflow_id: str, type: str, payload: Dict[str, Any]
    ) -> None:
        """Create a generic event for a workflow.

        Args:
            workflow_id: Target workflow identifier
            event_type: Type of the event (e.g., 'CUSTOM_EVENT')
            payload: Event data payload
        """
        await self.execute(
            """
            INSERT INTO events (workflow_id, type, payload)
            VALUES (?, ?, ?)
            """,
            (workflow_id, type, json.dumps(payload)),
        )

    async def create_signal_event(
        self, workflow_id: str, name: str, payload: Dict[str, Any]
    ) -> None:
        """Create a signal event for a running workflow.

        Signals can be sent to workflows to trigger conditional logic or
        provide external input during execution.

        Args:
            workflow_id: Target workflow identifier
            name: Signal name/identifier
            payload: Signal data payload

        Raises:
            WorkflowNotFoundError: If the workflow doesn't exist
            RuntimeError: If the workflow is not in RUNNING state
        """
        # Verify workflow exists and is running
        row = await self.fetchone(
            """
            SELECT id, status
            FROM workflows
            WHERE id = ?
            """,
            (workflow_id,),
        )

        if not row:
            raise WorkflowNotFoundError(f"Workflow with ID {workflow_id} not found.")

        if row["status"] != "RUNNING":
            raise RuntimeError(
                f"Cannot signal workflow with ID {workflow_id} because it is not running."
            )

        # Create signal event
        signal_payload = {
            "name": name,
            "payload": payload,
            "sent_at": datetime.now(timezone.utc).isoformat(),
        }

        await self.execute(
            """
            INSERT INTO events (workflow_id, type, payload)
            VALUES (?, 'SIGNAL_RECEIVED', ?)
            """,
            (workflow_id, json.dumps(signal_payload)),
        )

    async def workflow_failed(
        self,
        workflow_id: str,
        error: str,
        task_id: str | None = None,
        task_kind: str | None = None,
    ) -> None:
        """Mark a workflow as failed due to an unhandled exception.

        Creates a WORKFLOW_FAILED event and updates the workflow status.
        Also cancels any remaining pending tasks for the workflow.

        Args:
            workflow_id: Workflow identifier to mark as failed
            error: Error message describing the failure
            task_id: Optional task ID that caused the failure
            task_kind: Optional task kind that caused the failure

        Raises:
            WorkflowNotFoundError: If the workflow doesn't exist
        """
        # Get workflow info (this will raise WorkflowNotFoundError if not found)
        workflow = await self.get_workflow_info(workflow_id)

        # Skip if already in terminal state
        if workflow["status"] in ("COMPLETED", "FAILED", "CANCELED"):
            return

        # Prepare failure payload
        payload = {
            "error": error,
            "failed_at": datetime.now(timezone.utc).isoformat(),
        }
        if task_id:
            payload["task_id"] = task_id
        if task_kind:
            payload["task_kind"] = task_kind

        # Create failure event
        await self.execute(
            """
            INSERT INTO events (workflow_id, type, payload)
            VALUES (?, 'WORKFLOW_FAILED', ?)
            """,
            (workflow_id, json.dumps(payload)),
        )

        # Update workflow status
        await self.execute(
            """
            UPDATE workflows
            SET status = 'FAILED',
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (workflow_id,),
        )

        # Cancel all pending tasks
        await self.execute(
            """
            UPDATE tasks
            SET status = 'FAILED',
                last_error = 'workflow failed'
            WHERE workflow_id = ?
              AND status = 'PENDING'
            """,
            (workflow_id,),
        )

    async def complete_workflow(self, workflow_id: str) -> None:
        """Mark a workflow as successfully completed.

        Creates a WORKFLOW_COMPLETED event and updates the workflow status.
        Also completes any running step tasks for the workflow.

        Args:
            workflow_id: Workflow identifier to mark as completed

        Raises:
            WorkflowNotFoundError: If the workflow doesn't exist
        """
        # Get workflow info (this will raise WorkflowNotFoundError if not found)
        workflow = await self.get_workflow_info(workflow_id)

        # Skip if already in terminal state
        if workflow["status"] in ("COMPLETED", "FAILED", "CANCELED"):
            return

        # Create completion event
        await self.execute(
            """
            INSERT INTO events (workflow_id, type, payload)
            VALUES (?, 'WORKFLOW_COMPLETED', ?)
            """,
            (
                workflow_id,
                json.dumps({"completed_at": datetime.now(timezone.utc).isoformat()}),
            ),
        )

        # Update workflow status
        await self.execute(
            """
            UPDATE workflows
            SET status = 'COMPLETED',
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (workflow_id,),
        )

        # Complete any running step tasks
        await self.execute(
            """
            UPDATE tasks
            SET status = 'COMPLETED',
                updated_at = CURRENT_TIMESTAMP
            WHERE workflow_id = ?
              AND kind = 'STEP'
              AND status = 'RUNNING'
            """,
            (workflow_id,),
        )

    async def cancel_workflow(
        self, workflow_id: str, reason: str | None = None
    ) -> None:
        """Cancel a workflow and all its pending tasks.

        Cancellation marks the workflow as CANCELLED and fails all pending
        tasks associated with it. Already completed or failed workflows
        are left unchanged.

        Args:
            workflow_id: Workflow identifier to cancel
            reason: Optional cancellation reason

        Raises:
            WorkflowNotFoundError: If the workflow doesn't exist
        """
        # Verify workflow exists
        row = await self.fetchone(
            """
            SELECT id, status
            FROM workflows
            WHERE id = ?
            """,
            (workflow_id,),
        )

        if not row:
            raise WorkflowNotFoundError(f"Workflow with ID {workflow_id} not found.")

        # Skip if already in terminal state
        if row["status"] in ("COMPLETED", "FAILED", "CANCELED"):
            return

        # Prepare cancellation payload
        payload = {
            "reason": reason or "Cancelled",
            "canceled_at": datetime.now(timezone.utc).isoformat(),
        }

        # Create cancellation event
        await self.execute(
            """
            INSERT INTO events (workflow_id, type, payload)
            VALUES (?, 'WORKFLOW_CANCELLED', ?)
            """,
            (workflow_id, json.dumps(payload)),
        )

        # Update workflow status
        await self.execute(
            """
            UPDATE workflows
            SET status = 'CANCELLED'
            WHERE id = ?
            """,
            (workflow_id,),
        )

        # Fail all pending tasks
        await self.execute(
            """
            UPDATE tasks
            SET status = 'FAILED',
                last_error = 'workflow cancelled'
            WHERE workflow_id = ?
              AND status = 'PENDING'
            """,
            (workflow_id,),
        )

    # === Task Management Methods ===

    async def task_completed(self, task_id: str) -> None:
        """Mark a task as completed.

        Updates the task status to COMPLETED, indicating successful execution.

        Args:
            task_id: Unique identifier of the task to mark as completed
        """
        sql = """
                UPDATE tasks
                    SET status = 'COMPLETED',
                        updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                AND status = 'RUNNING'
                """
        await self.execute(sql, (task_id,))

    async def task_failed(self, task_id: str, error_message: str) -> None:
        """Mark a task as failed with an error message.

        Updates the task status to FAILED and records the error message.

        Args:
            task_id: Unique identifier of the task to mark as failed
            error_message: Error message describing the failure
        """
        sql = """
            UPDATE tasks
                SET status = 'FAILED',
                    last_error = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                AND status = 'RUNNING'
            """
        await self.execute(sql, (error_message, task_id))

    async def schedule_retry(self, task_id: str, run_at: datetime, error: str) -> None:
        """Schedule a task for retry.

        Updates the task status to PENDING and sets the next execution time.

        Args:
            task_id: Unique identifier of the task to retry
            run_at: Datetime when the task should be retried
            error: Error message from the failed attempt
        """
        sql = """
            UPDATE tasks
            SET status = 'PENDING',
                run_at = ?,
                last_error = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """
        await self.execute(sql, (run_at, error, task_id))

    async def claim_task(self) -> Task | None:
        """Atomically claim the next available task for processing.

        Claims a pending STEP task that is ready to run by updating its status
        to RUNNING and incrementing the attempt counter.

        Returns:
            Task object if a task was claimed, None if no tasks available
        """
        sql = """
            UPDATE tasks
                SET status = 'RUNNING',
                    attempts = attempts + 1,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = (
                    SELECT id
                    FROM tasks
                    WHERE status = 'PENDING'
                    AND run_at <= CURRENT_TIMESTAMP
                    ORDER BY run_at ASC, created_at ASC
                    LIMIT 1
                )
                RETURNING *;
        """

        row = await self.fetchone(sql)
        return Task(**row) if row else None  # type: ignore

    async def create_activity(
        self, workflow_id: str, metadata: ActivityMetadata
    ) -> None:
        """Create an activity task and corresponding event.

        Schedules an activity for execution by creating both an event record
        and a task record with retry configuration.

        Args:
            workflow_id: ID of the workflow that owns this activity
            metadata: Activity metadata including name, retry count, and timeout
        """
        activity_id = self._create_id()

        # SQL statements
        event_sql = """
            INSERT INTO events (workflow_id, type, payload)
            VALUES (?, 'ACTIVITY_SCHEDULED', ?)
        """

        task_sql = """
            INSERT INTO tasks (
                id, workflow_id, kind, target, run_at, status,
                attempts, max_attempts
            ) VALUES (?, ?, 'ACTIVITY', ?, CURRENT_TIMESTAMP, 'PENDING', 0, ?)
        """

        # Parameters
        event_params = (workflow_id, json.dumps(metadata))
        task_params = (
            activity_id,
            workflow_id,
            metadata["name"],
            metadata["retry_count"],
        )

        # Execute as transaction
        async with aiosqlite.connect(DATABASE) as conn:
            await conn.execute(event_sql, event_params)
            await conn.execute(task_sql, task_params)
            await conn.commit()

    async def get_activity_event(
        self, workflow_id: str, activity_name: str, attempts: int
    ) -> Event | None:
        """Retrieve the scheduled event for a specific activity.

        Args:
            workflow_id: ID of the workflow that owns the activity
            activity_name: Name of the activity
        Returns:
            Event object if found, None otherwise
        """
        sql = """
            SELECT type, payload
                FROM events
            WHERE workflow_id = ?
                AND type = 'ACTIVITY_SCHEDULED'
                AND payload->>'$.name' = ?
            ORDER BY id ASC
                LIMIT 1
            OFFSET ?
        """
        row = await self.fetchone(sql, (workflow_id, activity_name, attempts - 1))
        if not row:
            return None

        return Event(
            type=row["type"],
            payload=json.loads(row["payload"]),
        )

    async def create_timer(self, workflow_id: str, fire_at: datetime) -> None:
        """Create a timer task for a workflow.
        Schedules a timer task to wake up the workflow at a specific time.
        Args:
            workflow_id: ID of the workflow to schedule the timer for
            fire_at: Datetime when the timer should trigger
        """
        timer_id = self._create_id()

        await self.create_event(
            workflow_id,
            "TIMER_SCHEDULED",
            {
                "timer_id": timer_id,
                "fire_at": fire_at.isoformat(),
            },
        )

        await self.execute(
            """
                INSERT INTO tasks (
                    id, workflow_id, kind, target, run_at, status
                )
                VALUES (?, ?, 'TIMER', '__timer__', ?, 'PENDING')
            """,
            (timer_id, workflow_id, fire_at),
        )

    async def release_task(self, task_id: str) -> None:
        """
        Release a claimed task back to PENDING.
        Used when the task cannot be executed yet (e.g. TIMER not due).
        Args:
            task_id: Unique identifier of the task to release
        """
        await self.execute(
            """
            UPDATE tasks
            SET status = 'PENDING',
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            AND status = 'RUNNING'
            """,
            (task_id,),
        )

    async def rotate_workflow_driver(self, workflow_id: str) -> None:
        """
        Retire the currently running workflow driver and enqueue a new one.
        Called when an unblock event (activity/timer/signal) occurs.
        """

        id = self._create_id()

        workflow = await self.get_workflow_info(workflow_id)

        # 1. Complete old driver
        await self.execute(
            """
            UPDATE tasks
            SET status = 'COMPLETED',
                updated_at = CURRENT_TIMESTAMP
            WHERE workflow_id = ?
            AND kind = 'STEP'
            AND status = 'RUNNING'
            """,
            (workflow_id,),
        )

        # 2. Enqueue new driver
        await self.execute(
            """
            INSERT INTO tasks (
                id, workflow_id, kind, target, status, run_at
            )
            VALUES (?, ?, 'STEP', ?, 'PENDING', CURRENT_TIMESTAMP)
            """,
            (id, workflow_id, workflow["name"]),
        )

    async def complete_running_step(self, workflow_id: str):
        await self.execute(
            """
            UPDATE tasks
            SET status = 'COMPLETED',
                updated_at = CURRENT_TIMESTAMP
            WHERE workflow_id = ?
            AND kind = 'STEP'
            AND status = 'RUNNING'
            """,
            (workflow_id,),
        )

    async def workflow_is_completed(self, workflow_id: str) -> bool:
        row = await self.fetchone(
            """
            SELECT 1
            FROM events
            WHERE workflow_id = ?
            AND type = 'WORKFLOW_COMPLETED'
            LIMIT 1
            """,
            (workflow_id,),
        )
        return row is not None

    async def create_log(self, workflow_id: str, level: str, message: str) -> None:
        """Create a log entry for a workflow.

        Args:
            workflow_id: ID of the workflow to associate the log with
            level: Log level (e.g., 'INFO', 'ERROR')
            message: Log message content
        """
        await self.execute(
            """
            INSERT INTO logs (workflow_id, level, message, created_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (workflow_id, level, message),
        )

    # === Context Manager Methods ===

    async def __aenter__(self) -> "Database[InputT, StateT]":
        """Async context manager entry point."""
        await self._init_db()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        """Async context manager exit point."""
        pass

    # === Utility Methods ===

    def _create_id(self) -> str:
        """Generate a unique identifier using UUID4.

        Returns:
            Hexadecimal string representation of a UUID4
        """
        return uuid4().hex
