"""Loom - Durable workflow orchestration engine for Python.

This module provides the main API for creating and managing durable workflows.

Example:
    >>> import loom
    >>>
    >>> @loom.activity(name="greet", retry_count=3)
    >>> async def greet(name: str) -> str:
    ...     return f"Hello, {name}!"
    >>>
    >>> @loom.workflow(name="GreetingWorkflow", version="1.0.0")
    >>> class GreetingWorkflow(loom.Workflow[dict, dict]):
    ...     @loom.step(name="greet_step")
    ...     async def greet_step(self, ctx):
    ...         result = await ctx.activity(greet, ctx.input["name"])
    ...         await ctx.state.set("result", result)
"""

from loom.common.errors import (
    ActivityFailedError,
    NonDeterministicWorkflowError,
    WorkerCancelledError,
    WorkflowExecutionError,
    WorkflowNotFoundError,
    WorkflowStillRunningError,
)
from loom.core.context import WorkflowContext
from loom.core.runner import run_once
from loom.core.worker import WorkflowWorker, start_worker
from loom.core.workflow import Workflow
from loom.database.db import Database
from loom.decorators.activity import activity
from loom.decorators.workflow import step, workflow
from loom.schemas.state import Input, State

__version__ = "0.1.0"

__all__ = [
    # Decorators
    "activity",
    "workflow",
    "step",
    # Core classes
    "Workflow",
    "WorkflowContext",
    "Database",
    "WorkflowWorker",
    # Functions
    "start_worker",
    "run_once",
    # Version
    "__version__",
    # Schemas
    "State",
    "Input",
    # Exceptions
    "WorkflowNotFoundError",
    "WorkflowStillRunningError",
    "WorkflowExecutionError",
    "ActivityFailedError",
    "WorkerCancelledError",
    "NonDeterministicWorkflowError",
]


# Import app lazily to avoid circular imports
# This allows 'loom.web.main:app' to work for uvicorn
def __getattr__(name):
    if name == "app":
        from loom.web.main import app

        return app
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
