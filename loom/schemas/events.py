from typing import Any, Dict, Literal, Optional, TypedDict


class Event(TypedDict):
    """Represents a workflow event in the event store.

    Events are immutable records of things that happened during workflow
    execution, forming the single source of truth for workflow state.

    Attributes:
        type: Event type identifier (e.g., 'WORKFLOW_STARTED', 'ACTIVITY_COMPLETED')
        payload: Event-specific data payload containing relevant information
    """

    type: str
    payload: Dict[str, Any]


class WorkflowFailurePayload(TypedDict, total=False):
    """Payload structure for workflow failure events.

    Used when a workflow encounters an unrecoverable error during execution.

    Attributes:
        error: Error message describing what went wrong
        step: Name of the step where the failure occurred
        reason: High-level reason for the failure
        traceback: Full Python traceback for debugging
    """

    error: str
    step: str
    reason: str
    traceback: str


class ActivityFailurePayload(TypedDict, total=False):
    """Payload structure for activity failure events.

    Used when an activity fails and may be retried based on its configuration.

    Attributes:
        activity: Name of the failed activity
        error: Error message from the activity execution
        attempt: Current attempt number (for retry tracking)
    """

    activity: str
    error: str
    attempt: int


class ExtractedError(TypedDict, total=False):
    """Structured error information extracted from workflow or activity failures.

    Provides a normalized view of errors for monitoring and debugging purposes.

    Attributes:
        source: Whether the error originated from workflow logic or an activity
        message: Human-readable error message
        step: Workflow step name (if error occurred in workflow logic)
        activity: Activity name (if error occurred in an activity)
        details: Additional context-specific error information
    """

    source: Literal["WORKFLOW", "ACTIVITY"]
    message: str
    step: Optional[str]
    activity: Optional[str]
    details: Dict[str, Any]
