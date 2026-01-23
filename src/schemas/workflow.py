from datetime import datetime
from enum import Enum
from typing import Awaitable, Callable, TypedDict, TypeVar

StateT = TypeVar("StateT")

Func = TypeVar("Func", bound=Callable[..., Awaitable[object]])

InputT = TypeVar("InputT")

ClsT = TypeVar("ClsT")


class Step(TypedDict):
    name: str
    description: str
    fn: str


class WorkflowStatus(str, Enum):
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELED = "CANCELED"


class WorkflowInfo(TypedDict):
    id: str
    name: str
    status: WorkflowStatus
    module: str
    created_at: datetime
    updated_at: datetime
