from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Dict, Generic, Iterable, List

from ..schemas.activity import ActivityMetadata
from ..schemas.database import WorkflowInput
from ..schemas.events import Event
from ..schemas.tasks import Task
from ..schemas.workflow import InputT, StateT


class DatabaseBackend(ABC, Generic[InputT, StateT]):
    """Abstract base class for database backends.
    
    This class defines the interface that all database backends must implement
    to support the Loom workflow orchestration engine.
    
    Type Parameters:
        InputT: The input type for workflows
        StateT: The state type for workflows
    """
    
    @abstractmethod
    async def _init_db(self) -> None:
        """Initialize the database by creating directories and running migrations."""
        pass
    
    @abstractmethod
    async def query(self, sql: str, params: tuple = ()) -> Iterable[Any]:
        """Execute a SELECT query and return all results."""
        pass
    
    @abstractmethod
    async def fetchone(self, sql: str, params: tuple = ()) -> Any | None:
        """Execute a SELECT query and return the first result."""
        pass
    
    @abstractmethod
    async def execute(self, sql: str, params: tuple = ()) -> None:
        """Execute a SQL statement (INSERT, UPDATE, DELETE)."""
        pass
    
    # === Workflow Query Methods ===
    
    @abstractmethod
    async def get_workflow_events(self, workflow_id: str) -> List[Event]:
        """Retrieve all events for a specific workflow in chronological order."""
        pass
    
    @abstractmethod
    async def get_workflow_info(self, workflow_id: str) -> Dict[str, Any]:
        """Retrieve complete information for a specific workflow."""
        pass
    
    @abstractmethod
    async def get_workflow_status(self, workflow_id: str) -> str:
        """Retrieve only the status of a specific workflow (optimized query)."""
        pass
    
    # === Workflow Management Methods ===
    
    @abstractmethod
    async def recreate_workflow_task(self, workflow_id: str) -> None:
        """Recreate the initial task for a workflow."""
        pass
    
    @abstractmethod
    async def create_workflow(self, workflow: WorkflowInput, input: InputT) -> str:
        """Create a new workflow instance with initial state."""
        pass
    
    @abstractmethod
    async def create_event(
        self, workflow_id: str, type: str, payload: Dict[str, Any]
    ) -> None:
        """Create a generic event for a workflow."""
        pass
    
    @abstractmethod
    async def create_signal_event(
        self, workflow_id: str, name: str, payload: Dict[str, Any]
    ) -> None:
        """Create a signal event for a running workflow."""
        pass
    
    @abstractmethod
    async def workflow_failed(
        self,
        workflow_id: str,
        error: str,
        task_id: str | None = None,
        task_kind: str | None = None,
    ) -> None:
        """Mark a workflow as failed due to an unhandled exception."""
        pass
    
    @abstractmethod
    async def complete_workflow(self, workflow_id: str) -> None:
        """Mark a workflow as successfully completed."""
        pass
    
    @abstractmethod
    async def cancel_workflow(
        self, workflow_id: str, reason: str | None = None
    ) -> None:
        """Cancel a workflow and all its pending tasks."""
        pass
    
    # === Task Management Methods ===
    
    @abstractmethod
    async def task_completed(self, task_id: str) -> None:
        """Mark a task as completed."""
        pass
    
    @abstractmethod
    async def task_failed(self, task_id: str, error_message: str) -> None:
        """Mark a task as failed with an error message."""
        pass
    
    @abstractmethod
    async def schedule_retry(self, task_id: str, run_at: datetime, error: str) -> None:
        """Schedule a task for retry."""
        pass
    
    @abstractmethod
    async def claim_task(self) -> Task | None:
        """Atomically claim the next available task for processing."""
        pass
    
    @abstractmethod
    async def create_activity(
        self, workflow_id: str, metadata: ActivityMetadata
    ) -> None:
        """Create an activity task and corresponding event."""
        pass
    
    @abstractmethod
    async def get_activity_event(
        self, workflow_id: str, activity_name: str, attempts: int
    ) -> Event | None:
        """Retrieve the scheduled event for a specific activity."""
        pass
    
    @abstractmethod
    async def create_timer(self, workflow_id: str, fire_at: datetime) -> None:
        """Create a timer task for a workflow."""
        pass
    
    @abstractmethod
    async def release_task(self, task_id: str) -> None:
        """Release a claimed task back to PENDING."""
        pass
    
    @abstractmethod
    async def rotate_workflow_driver(self, workflow_id: str) -> None:
        """Retire the currently running workflow driver and enqueue a new one."""
        pass
    
    @abstractmethod
    async def complete_running_step(self, workflow_id: str) -> None:
        """Complete the currently running step task for a workflow."""
        pass
    
    @abstractmethod
    async def workflow_is_completed(self, workflow_id: str) -> bool:
        """Check if a workflow has completed."""
        pass
    
    @abstractmethod
    async def create_log(self, workflow_id: str, level: str, message: str) -> None:
        """Create a log entry for a workflow."""
        pass
    
    # === Context Manager Methods ===
    
    async def __aenter__(self) -> "DatabaseBackend[InputT, StateT]":
        """Async context manager entry point."""
        await self._init_db()
        return self
    
    async def __aexit__(self, exc_type, exc, tb) -> None:
        """Async context manager exit point."""
        pass
    
    # === Utility Methods ===
    
    @abstractmethod
    def _create_id(self) -> str:
        """Generate a unique identifier."""
        pass
