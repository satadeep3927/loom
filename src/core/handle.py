from datetime import datetime
from typing import Any, Dict, Generic, Iterable, List

from ..common.errors import (
    WorkerCancelledError,
    WorkflowExecutionError,
    WorkflowStillRunningError,
)
from ..database.db import Database
from ..schemas.events import (
    ActivityFailurePayload,
    Event,
    ExtractedError,
    WorkflowFailurePayload,
)
from ..schemas.workflow import InputT, StateT, WorkflowInfo


class WorkflowHandle(Generic[InputT, StateT]):
    """
    Handle for managing workflows.
    """

    id: str

    def __init__(self, id: str) -> None:
        self.id = id

    async def info(self) -> WorkflowInfo:
        async with Database[InputT, StateT]() as db:
            row = await db.get_workflow_info(self.id)

        return WorkflowInfo(
            id=row["id"],
            name=row["name"],
            status=row["status"],
            module=row["module"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    async def status(self) -> str:
        """Get workflow status efficiently without fetching all info."""
        async with Database[InputT, StateT]() as db:
            return await db.get_workflow_status(self.id)

    async def result(self) -> StateT:
        # Check status first to avoid unnecessary work
        async with Database[InputT, StateT]() as db:
            status = await db.get_workflow_status(self.id)

        if status == "RUNNING":
            raise WorkflowStillRunningError(
                "Workflow is still running; result is not available."
            )

        async with Database[InputT, StateT]() as db:
            events = await db.get_workflow_events(self.id)

        state = self._replay_state(events)

        if status == "FAILED":
            error = self._extract_error(events)
            raise WorkflowExecutionError(error)
        if status == "CANCELED":
            raise WorkerCancelledError("Workflow was canceled; no result is available.")

        return state

    async def signal(self, name: str, payload: Dict[str, Any]) -> None:
        # Validate signal name and payload.
        if not name:
            raise ValueError("Signal name must be a non-empty string.")
        if not isinstance(payload, dict):
            raise ValueError("Signal payload must be a dictionary.")

        async with Database[InputT, StateT]() as db:
            await db.create_signal_event(self.id, name, payload)

    def _replay_state(self, events: List[Event]) -> StateT:
        """Replay workflow state from events with optimized processing."""
        # Initialize as dict since we don't know the concrete StateT type at runtime
        state_dict = {}

        for event in events:
            event_type = event["type"]

            if event_type == "STATE_SET":
                try:
                    payload = event["payload"]
                    state_dict[payload["key"]] = payload["value"]
                except (KeyError, TypeError):
                    continue

            elif event_type == "STATE_UPDATE":
                try:
                    payload = event["payload"]
                    state_dict.update(payload)
                except TypeError:
                    continue

        return state_dict  # type: ignore

    def _extract_error(self, events: Iterable[Event]) -> ExtractedError:
        """
        Extract the most relevant failure from workflow events.

        Rules:
        - Prefer WORKFLOW_FAILED over ACTIVITY_FAILED
        - Use the last failure event
        - Never raise from this method
        """

        last_workflow_failure: WorkflowFailurePayload | None = None
        last_activity_failure: ActivityFailurePayload | None = None

        for event in events:
            etype = event["type"]
            payload = event.get("payload", {})

            if etype == "WORKFLOW_FAILED":
                last_workflow_failure = payload  # type: ignore

            elif etype == "ACTIVITY_FAILED":
                last_activity_failure = payload  # type: ignore

        if last_workflow_failure:
            return {
                "source": "WORKFLOW",
                "message": last_workflow_failure.get("error", "Workflow failed"),
                "step": last_workflow_failure.get("step"),
                "details": dict(last_workflow_failure),
            }

        if last_activity_failure:
            return {
                "source": "ACTIVITY",
                "message": last_activity_failure.get("error", "Activity failed"),
                "activity": last_activity_failure.get("activity"),
                "details": dict(last_activity_failure),
            }

        # Defensive fallback
        return {
            "source": "WORKFLOW",
            "message": "Workflow failed for unknown reasons",
            "details": {},
        }

    @classmethod
    def with_id(cls, id: str) -> "WorkflowHandle[InputT, StateT]":
        """
        Create a new WorkflowHandle with the specified ID.

        Args:
            id: The workflow ID to associate with the handle.

        Returns:
            A new WorkflowHandle instance with the given ID.

        Example:
            ```python
            handle = WorkflowHandle.with_id("workflow-1234")
            ```
        """
        return cls(id)
