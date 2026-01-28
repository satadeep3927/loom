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

from src.core.context import WorkflowContext
from src.core.runner import run_once
from src.core.worker import WorkflowWorker, start_worker
from src.core.workflow import Workflow
from src.database.db import Database
from src.decorators.activity import activity
from src.decorators.workflow import step, workflow

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
]
