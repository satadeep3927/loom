from datetime import datetime
from typing import Literal, TypedDict

# Task kind types matching database CHECK constraint
TaskKind = Literal["STEP", "ACTIVITY", "TIMER"]

# Task status types matching database CHECK constraint
TaskStatus = Literal["PENDING", "RUNNING", "COMPLETED", "FAILED"]


class Task(TypedDict):
    """
    Task schema matching the database tasks table structure.

    Tasks represent units of work in the workflow execution queue,
    including workflow steps, activity executions, and timer events.
    """

    id: str
    workflow_id: str
    kind: TaskKind
    target: str
    run_at: str
    status: TaskStatus
    attempts: int
    max_attempts: int
    last_error: str | None
    created_at: str
    updated_at: str


class TaskInput(TypedDict):
    """
    Input schema for creating new tasks.

    Excludes auto-generated fields like timestamps and attempts.
    """

    id: str
    workflow_id: str
    kind: TaskKind
    target: str
    run_at: datetime
    status: TaskStatus
    max_attempts: int


class TaskUpdate(TypedDict, total=False):
    """
    Schema for updating existing tasks.

    All fields are optional to allow partial updates.
    """

    status: TaskStatus
    attempts: int
    last_error: str | None
    updated_at: datetime
