from math import e
from typing import Any, Awaitable, Callable, List

from ..common.errors import StopReplay
from ..database.db import Database
from ..schemas.activity import ActivityMetadata
from ..schemas.events import Event


class WorkflowContext[InputT, StateT]:
    """Execution context for workflow steps with replay capabilities.

    The WorkflowContext provides a controlled execution environment for workflow
    steps, managing event history replay, state reconstruction, and activity
    scheduling. It enforces deterministic execution by controlling access to
    external resources and side effects.

    Type Parameters:
        InputT: Immutable input type for the workflow
        StateT: Mutable state type that gets reconstructed during replay

    Attributes:
        id: Unique workflow identifier
        input: Immutable workflow input data
        history: Chronological list of workflow events
        state: Current mutable workflow state
        cursor: Current position in event history during replay
    """

    id: str
    input: InputT
    history: List[Event]
    state: StateT
    cursor: int = 0

    def __init__(
        self, id: str, input: InputT, history: List[Event], state: StateT
    ) -> None:
        """Initialize workflow context with replay state.

        Args:
            id: Unique workflow identifier
            input: Immutable workflow input data
            history: List of events for replay
            state: Current workflow state
        """
        self.id = id
        self.input = input
        self.history = history
        self.state = state

    # === Private Replay Management Methods ===

    def _peek(self) -> Event | None:
        """Look at the next event in history without consuming it.

        Returns:
            Next event in history or None if at end
        """
        if self.cursor >= len(self.history):
            return None
        return self.history[self.cursor]

    def _consume(self) -> Event:
        """Consume and return the next event in history.

        Returns:
            Next event in history

        Raises:
            RuntimeError: If no event is available to consume
        """
        event = self._peek()
        if event is None:
            raise RuntimeError("No event available to consume")
        self.cursor += 1
        return event

    def _extract_activity_metadata[FuncReturn](
        self, fn: Callable[..., Awaitable[FuncReturn]], args: tuple[Any, ...]
    ) -> ActivityMetadata:
        """Extract metadata from an activity function for scheduling.

        Retrieves activity configuration attributes that were set by the
        @activity decorator, including retry settings and timeout values.

        Args:
            fn: Activity function to extract metadata from
            args: Arguments that will be passed to the activity

        Returns:
            ActivityMetadata dictionary with function metadata
        """
        return {
            "name": getattr(fn, "_activity_name", fn.__name__),
            "description": getattr(fn, "_activity_description", ""),
            "retry_count": getattr(fn, "_activity_retry_count", 0),
            "timeout_seconds": getattr(fn, "_activity_timeout_seconds", 0),
            "func": fn.__name__,
            "module": fn.__module__,
            "args": list(args),
        }

    # === Public Activity Execution Methods ===

    async def activity[FuncReturn](
        self,
        fn: Callable[..., Awaitable[FuncReturn]],
        *args,
    ) -> FuncReturn:
        """Execute an activity with replay-safe semantics.

        During replay, returns the cached result from history if the activity
        was already completed. During initial execution or after replay,
        schedules the activity for execution and stops replay to allow the
        worker to process it.

        Args:
            fn: Activity function to execute
            *args: Arguments to pass to the activity function

        Returns:
            Activity result (from cache during replay, or after execution)

        Raises:
            StopReplay: When activity needs to be scheduled or is pending
        """
        metadata = self._extract_activity_metadata(fn, args)
        while True:
            event = self._peek()
            if not event:
                break

            if event["type"] == "WORKFLOW_STARTED":
                # bootstrap event – already handled elsewhere or handle here
                self._consume()
                continue

            if event["type"] not in (
                "ACTIVITY_SCHEDULED",
                "ACTIVITY_COMPLETED",
            ):
                # some other event (STATE_SET, etc.)
                self._consume()
                continue

            # now we are at an activity-related event
            break
        event = self._peek()

        print(event)

        # Return cached result if activity was already completed
        if event and event["type"] == "ACTIVITY_SCHEDULED":
            assert event["payload"]["name"] == metadata["name"]
            self._consume()  # IMPORTANT: consume scheduled

            next_event = self._peek()
            if next_event and next_event["type"] == "ACTIVITY_COMPLETED":
                assert next_event["payload"]["name"] == metadata["name"]
                completed = self._consume()
                return completed["payload"]["result"]

            # Scheduled but not yet completed
            raise StopReplay

        # Case: completed without scheduled (should not happen, but be defensive)
        if event and event["type"] == "ACTIVITY_COMPLETED":
            assert event["payload"]["name"] == metadata["name"]
            completed = self._consume()
            return completed["payload"]["result"]

        # Schedule new activity for execution
        async with Database[InputT, StateT]() as db:
            await db.create_activity(
                workflow_id=self.id,
                metadata=metadata,
            )

        raise StopReplay
