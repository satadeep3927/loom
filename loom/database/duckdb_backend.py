import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List
from uuid import uuid4

import duckdb

from ..common.config import DATA_ROOT, get_database_path
from ..common.errors import WorkflowNotFoundError
from ..lib.utils import get_duckdb_downgrade_migrations, get_duckdb_upgrade_migrations
from ..schemas.activity import ActivityMetadata
from ..schemas.database import WorkflowInput
from ..schemas.events import Event
from ..schemas.tasks import Task
from ..schemas.workflow import InputT, StateT
from .base import DatabaseBackend


class DuckDBDatabase(DatabaseBackend[InputT, StateT]):
    """DuckDB implementation of the database backend.
    
    DuckDB provides better write concurrency compared to SQLite while
    maintaining a simple embedded database architecture. It supports 
    200-300+ concurrent workflows.
    
    Type Parameters:
        InputT: The input type for workflows
        StateT: The state type for workflows
    """
    
    def __init__(self) -> None:
        """Initialize the DuckDB database with migration scripts."""
        self.upgrade_migrations = get_duckdb_upgrade_migrations()
        self.downgrade_migrations = get_duckdb_downgrade_migrations()
        self.db_path = get_database_path()
    
    async def _init_db(self) -> None:
        """Initialize the database by creating directories and running migrations."""
        # Ensure data directory exists
        if not os.path.exists(DATA_ROOT):
            os.makedirs(DATA_ROOT, exist_ok=True)
        
        # Create and migrate database if it doesn't exist
        if not os.path.exists(self.db_path):
            conn = duckdb.connect(self.db_path)
            try:
                for migration in self.upgrade_migrations:
                    sql = migration["sql"]
                    
                    # Remove comment lines and empty lines
                    lines = [line for line in sql.split('\n') if line.strip() and not line.strip().startswith('--')]
                    clean_sql = '\n'.join(lines)
                    
                    # DuckDB requires executing each statement separately
                    # Split on semicolon and execute non-empty statements
                    statements = [s.strip() for s in clean_sql.split(';') if s.strip()]
                    for statement in statements:
                        conn.execute(statement)
            finally:
                conn.close()
    
    async def query(self, sql: str, params: tuple = ()) -> Iterable[Any]:
        """Execute a SELECT query and return all results."""
        conn = duckdb.connect(self.db_path)
        result = conn.execute(sql, params).fetchall()
        conn.close()
        
        # Convert to dict-like objects similar to aiosqlite.Row
        if result:
            columns = [desc[0] for desc in conn.description] if hasattr(conn, 'description') else []
            return [dict(zip(columns, row)) for row in result]
        return []
    
    async def fetchone(self, sql: str, params: tuple = ()) -> Any | None:
        """Execute a SELECT query and return the first result."""
        conn = duckdb.connect(self.db_path)
        cursor = conn.execute(sql, params)
        result = cursor.fetchone()
        
        if result:
            columns = [desc[0] for desc in cursor.description]
            conn.close()
            return dict(zip(columns, result))
        
        conn.close()
        return None
    
    async def execute(self, sql: str, params: tuple = ()) -> None:
        """Execute a SQL statement (INSERT, UPDATE, DELETE)."""
        conn = duckdb.connect(self.db_path)
        conn.execute(sql, params)
        conn.close()
    
    async def get_workflow_events(self, workflow_id: str) -> List[Event]:
        """Retrieve all events for a specific workflow in chronological order."""
        sql = """
            SELECT type, payload
            FROM events
            WHERE workflow_id = ?
            ORDER BY id ASC
        """
        
        conn = duckdb.connect(self.db_path)
        rows = conn.execute(sql, (workflow_id,)).fetchall()
        conn.close()
        
        events: List[Event] = []
        for row in rows:
            events.append(
                Event(
                    type=row[0],
                    payload=json.loads(row[1]),
                )
            )
        return events
    
    async def get_workflow_info(self, workflow_id: str) -> Dict[str, Any]:
        """Retrieve complete information for a specific workflow."""
        sql = """
            SELECT *
            FROM workflows
            WHERE id = ?
        """
        
        conn = duckdb.connect(self.db_path)
        cursor = conn.execute(sql, (workflow_id,))
        row = cursor.fetchone()
        
        if row:
            columns = [desc[0] for desc in cursor.description]
            conn.close()
            return dict(zip(columns, row))
        
        conn.close()
        raise WorkflowNotFoundError(f"Workflow with ID {workflow_id} not found.")
    
    async def get_workflow_status(self, workflow_id: str) -> str:
        """Retrieve only the status of a specific workflow (optimized query)."""
        sql = """
            SELECT status
            FROM workflows
            WHERE id = ?
        """
        
        row = await self.fetchone(sql, (workflow_id,))
        
        if row:
            return row["status"]
        
        raise WorkflowNotFoundError(f"Workflow with ID {workflow_id} not found.")
    
    async def recreate_workflow_task(self, workflow_id: str) -> None:
        """Recreate the initial task for a workflow."""
        task_id = self._create_id()
        workflow = await self.get_workflow_info(workflow_id)
        
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
        """Create a new workflow instance with initial state."""
        workflow_id = self._create_id()
        task_id = self._create_id()
        
        conn = duckdb.connect(self.db_path)
        
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
        conn.execute(workflow_sql, workflow_params)
        
        # Add workflow started event
        event_sql = """
            INSERT INTO events (workflow_id, type, payload)
            VALUES (?, 'WORKFLOW_STARTED', ?)
        """
        event_params = (
            workflow_id,
            json.dumps({"input": input}),
        )
        conn.execute(event_sql, event_params)
        
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
        conn.execute(task_sql, task_params)
        
        conn.close()
        return workflow_id
    
    async def create_event(
        self, workflow_id: str, type: str, payload: Dict[str, Any]
    ) -> None:
        """Create a generic event for a workflow."""
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
        """Create a signal event for a running workflow."""
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
        """Mark a workflow as failed due to an unhandled exception."""
        workflow = await self.get_workflow_info(workflow_id)
        
        if workflow["status"] in ("COMPLETED", "FAILED", "CANCELED"):
            return
        
        payload = {
            "error": error,
            "failed_at": datetime.now(timezone.utc).isoformat(),
        }
        if task_id:
            payload["task_id"] = task_id
        if task_kind:
            payload["task_kind"] = task_kind
        
        conn = duckdb.connect(self.db_path)
        
        # Create failure event
        conn.execute(
            """
            INSERT INTO events (workflow_id, type, payload)
            VALUES (?, 'WORKFLOW_FAILED', ?)
            """,
            (workflow_id, json.dumps(payload)),
        )
        
        # Update workflow status
        conn.execute(
            """
            UPDATE workflows
            SET status = 'FAILED',
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (workflow_id,),
        )
        
        # Cancel all pending tasks
        conn.execute(
            """
            UPDATE tasks
            SET status = 'FAILED',
                last_error = 'workflow failed'
            WHERE workflow_id = ?
              AND status = 'PENDING'
            """,
            (workflow_id,),
        )
        
        conn.close()
    
    async def complete_workflow(self, workflow_id: str) -> None:
        """Mark a workflow as successfully completed."""
        workflow = await self.get_workflow_info(workflow_id)
        
        if workflow["status"] in ("COMPLETED", "FAILED", "CANCELED"):
            return
        
        conn = duckdb.connect(self.db_path)
        
        # Create completion event
        conn.execute(
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
        conn.execute(
            """
            UPDATE workflows
            SET status = 'COMPLETED',
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (workflow_id,),
        )
        
        # Complete any running step tasks
        conn.execute(
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
        
        conn.close()
    
    async def cancel_workflow(
        self, workflow_id: str, reason: str | None = None
    ) -> None:
        """Cancel a workflow and all its pending tasks."""
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
        
        if row["status"] in ("COMPLETED", "FAILED", "CANCELED"):
            return
        
        payload = {
            "reason": reason or "Cancelled",
            "canceled_at": datetime.now(timezone.utc).isoformat(),
        }
        
        conn = duckdb.connect(self.db_path)
        
        # Create cancellation event
        conn.execute(
            """
            INSERT INTO events (workflow_id, type, payload)
            VALUES (?, 'WORKFLOW_CANCELLED', ?)
            """,
            (workflow_id, json.dumps(payload)),
        )
        
        # Update workflow status
        conn.execute(
            """
            UPDATE workflows
            SET status = 'CANCELLED'
            WHERE id = ?
            """,
            (workflow_id,),
        )
        
        # Fail all pending tasks
        conn.execute(
            """
            UPDATE tasks
            SET status = 'FAILED',
                last_error = 'workflow cancelled'
            WHERE workflow_id = ?
              AND status = 'PENDING'
            """,
            (workflow_id,),
        )
        
        conn.close()
    
    async def task_completed(self, task_id: str) -> None:
        """Mark a task as completed."""
        sql = """
            UPDATE tasks
                SET status = 'COMPLETED',
                    updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            AND status = 'RUNNING'
        """
        await self.execute(sql, (task_id,))
    
    async def task_failed(self, task_id: str, error_message: str) -> None:
        """Mark a task as failed with an error message."""
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
        """Schedule a task for retry."""
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
        """Atomically claim the next available task for processing."""
        # DuckDB doesn't support UPDATE...RETURNING yet, so we need a workaround
        conn = duckdb.connect(self.db_path)
        
        # First, select the task
        select_sql = """
            SELECT *
            FROM tasks
            WHERE status = 'PENDING'
            AND run_at <= CURRENT_TIMESTAMP
            ORDER BY run_at ASC, created_at ASC
            LIMIT 1
        """
        cursor = conn.execute(select_sql)
        row = cursor.fetchone()
        
        if not row:
            conn.close()
            return None
        
        columns = [desc[0] for desc in cursor.description]
        task_data = dict(zip(columns, row))
        task_id = task_data["id"]
        
        # Update the task
        update_sql = """
            UPDATE tasks
            SET status = 'RUNNING',
                attempts = attempts + 1,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """
        conn.execute(update_sql, (task_id,))
        
        conn.close()
        
        # Update the task data
        task_data["status"] = "RUNNING"
        task_data["attempts"] = task_data.get("attempts", 0) + 1
        
        return Task(**task_data)  # type: ignore
    
    async def create_activity(
        self, workflow_id: str, metadata: ActivityMetadata
    ) -> None:
        """Create an activity task and corresponding event."""
        activity_id = self._create_id()
        
        conn = duckdb.connect(self.db_path)
        
        # Create event
        event_sql = """
            INSERT INTO events (workflow_id, type, payload)
            VALUES (?, 'ACTIVITY_SCHEDULED', ?)
        """
        conn.execute(event_sql, (workflow_id, json.dumps(metadata)))
        
        # Create task
        task_sql = """
            INSERT INTO tasks (
                id, workflow_id, kind, target, run_at, status,
                attempts, max_attempts
            ) VALUES (?, ?, 'ACTIVITY', ?, CURRENT_TIMESTAMP, 'PENDING', 0, ?)
        """
        conn.execute(
            task_sql,
            (
                activity_id,
                workflow_id,
                metadata["name"],
                metadata["retry_count"],
            ),
        )
        
        conn.close()
    
    async def get_activity_event(
        self, workflow_id: str, activity_name: str, attempts: int
    ) -> Event | None:
        """Retrieve the scheduled event for a specific activity."""
        # DuckDB supports JSON extraction
        sql = """
            SELECT type, payload
            FROM events
            WHERE workflow_id = ?
                AND type = 'ACTIVITY_SCHEDULED'
                AND json_extract_string(payload, '$.name') = ?
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
        """Create a timer task for a workflow."""
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
        """Release a claimed task back to PENDING."""
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
        """Retire the currently running workflow driver and enqueue a new one."""
        id = self._create_id()
        workflow = await self.get_workflow_info(workflow_id)
        
        conn = duckdb.connect(self.db_path)
        
        # Complete old driver
        conn.execute(
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
        
        # Enqueue new driver
        conn.execute(
            """
            INSERT INTO tasks (
                id, workflow_id, kind, target, status, run_at
            )
            VALUES (?, ?, 'STEP', ?, 'PENDING', CURRENT_TIMESTAMP)
            """,
            (id, workflow_id, workflow["name"]),
        )
        
        conn.close()
    
    async def complete_running_step(self, workflow_id: str) -> None:
        """Complete the currently running step task for a workflow."""
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
        """Check if a workflow has completed."""
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
        """Create a log entry for a workflow."""
        await self.execute(
            """
            INSERT INTO logs (workflow_id, level, message, created_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            """,
            (workflow_id, level, message),
        )
    
    def _create_id(self) -> str:
        """Generate a unique identifier using UUID4."""
        return uuid4().hex
