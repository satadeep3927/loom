import datetime
from datetime import timedelta
from typing import Any, Awaitable, Callable, Generic, List

from ..common.errors import NonDeterministicWorkflowError, StopReplay
from ..database.db import Database
from ..schemas.activity import ActivityMetadata
from ..schemas.events import Event
from ..schemas.workflow import InputT, StateT
from .logger import WorkflowLogger
from .state import StateProxy


class WorkflowContext(Generic[InputT, StateT]):
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
    state: StateProxy[InputT, StateT]
    cursor: int = 0
    logger: WorkflowLogger
    _original_history_length: int  # Track original history size for replay detection

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
        self._original_history_length = len(history)  # Remember original size
        self.state = StateProxy(self, state)
        self.logger = WorkflowLogger(self)

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

    def _skip_step_events(self) -> None:
        """Skip over STEP_START and STEP_END events during replay.

        These are internal workflow management events that don't affect
        the deterministic execution logic.
        """
        while True:
            event = self._peek()
            if event and event["type"] in ("STEP_START", "STEP_END"):
                self._consume()
            else:
                break

    def _match_event(self, expected_type: str) -> Event | None:
        """
        Safe helper to check if the NEXT event matches what we expect.
        Returns the event if it matches (does NOT consume).
        Returns None if the next event is something else (or end of history).
        """
        event = self._peek()
        if event and event["type"] == expected_type:
            return event
        return None

    @property
    def is_replaying(self) -> bool:
        """Check if the workflow is currently replaying old events.

        Returns:
            True if replaying historical events, False if executing new logic
        """
        # We're replaying if we haven't consumed all the original events yet
        return self.cursor < self._original_history_length

    def is_at_end_of_history(self) -> bool:
        """Check if we've consumed all events in history.

        Returns:
            True if we're at the end of event history, False otherwise
        """
        return self.cursor >= len(self.history)

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
        metadata = self._extract_activity_metadata(fn, args)

        # Skip any step events first
        self._skip_step_events()
        scheduled_event = self._match_event("ACTIVITY_SCHEDULED")

        if scheduled_event:
            if scheduled_event["payload"]["name"] != metadata["name"]:
                raise NonDeterministicWorkflowError(
                    f"Replay mismatch: Expected activity {metadata['name']}, "
                    f"found {scheduled_event['payload']['name']} in history."
                )

            self._consume()

            # Skip step events before checking for completion
            self._skip_step_events()
            completed_event = self._match_event("ACTIVITY_COMPLETED")

            if completed_event:
                self._consume()
                return completed_event["payload"]["result"]  # type: ignore

            raise StopReplay

        # Skip step events before checking for unexpected events
        self._skip_step_events()
        unexpected_event = self._peek()
        if unexpected_event:
            raise NonDeterministicWorkflowError(
                f"Replay mismatch: Code wants to schedule activity {metadata['name']}, "
                f"but history contains {unexpected_event['type']}."
            )

        async with Database[InputT, StateT]() as db:
            await db.create_activity(
                workflow_id=self.id,
                metadata=metadata,
            )

        raise StopReplay

    async def sleep(
        self, delta: timedelta | None = None, until: datetime.datetime | None = None
    ) -> None:
        if delta is None and until is None:
            raise ValueError("Either 'delta' or 'until' must be provided")

        fire_at: datetime.datetime = (
            datetime.datetime.now(datetime.timezone.utc) + delta if delta else until  # type: ignore
        )

        # Skip any step events first
        self._skip_step_events()

        scheduled_event = self._match_event("TIMER_SCHEDULED")

        if scheduled_event:
            self._consume()

            # Skip step events before checking for timer fired
            self._skip_step_events()
            fired_event = self._match_event("TIMER_FIRED")
            if fired_event:
                self._consume()
                return  # Timer is done

            raise StopReplay

        # Skip step events before checking for unexpected events
        self._skip_step_events()
        unexpected_event = self._peek()
        if unexpected_event:
            raise NonDeterministicWorkflowError(
                f"Replay mismatch: Code wants to sleep, "
                f"but history contains {unexpected_event['type']}."
            )

        async with Database[InputT, StateT]() as db:
            await db.create_timer(self.id, fire_at)

        raise StopReplay

    async def wait_until_signal(self, signal_name: str) -> Any:
        """Pauses the workflow until a specific signal is received.

        If the signal is already in history (replay), it returns the data immediately.
        If not, it raises StopReplay to suspend execution until the signal arrives.
        """
        # Skip any step events first
        self._skip_step_events()
        # 1. Check if the signal is next in history
        event = self._match_event("SIGNAL_RECEIVED")

        if event:
            # STRICT CHECK: Ensure this is the signal we are waiting for.
            # If the history has "Signal B" but we are waiting for "Signal A",
            # it means the code logic has changed or the flow is non-deterministic.
            if event["payload"]["name"] != signal_name:
                raise NonDeterministicWorkflowError(
                    f"Replay mismatch: Expected signal '{signal_name}', "
                    f"but history contains signal '{event['payload']['name']}'."
                )

            self._consume()
            return event["payload"]["data"]

        # Skip step events before checking for unexpected events
        self._skip_step_events()
        unexpected_event = self._peek()
        if unexpected_event:
            raise NonDeterministicWorkflowError(
                f"Replay mismatch: Workflow expecting signal '{signal_name}', "
                f"but history contains {unexpected_event['type']}."
            )

        self.logger.info(f"Waiting for signal: {signal_name}")
        raise StopReplay

    def last_emitted_event_type(self) -> str | None:
        """Get the type of the last emitted event in the history."""
        return self.history[-1]["type"]

    async def _append_event(self, type: str, payload: dict[str, Any]) -> None:
        """Append a new event to the workflow's event history in the database.

        Args:
            type: Type of the event to append
            payload: Payload data for the event
        """
        async with Database[InputT, StateT]() as db:
            await db.create_event(
                workflow_id=self.id,
                type=type,
                payload=payload,
            )
        self.history.append({"type": type, "payload": payload})
