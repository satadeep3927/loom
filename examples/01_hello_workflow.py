"""Example 1: Hello World Workflow

Demonstrates:
- Basic workflow definition using @loom.workflow
- Simple activity execution with @loom.activity
- State management
"""

import asyncio
import sys
from pathlib import Path

from loom.schemas.state import Input, State

# Add src to path for development
sys.path.insert(0, str(Path(__file__).parent.parent))

import loom


# Define input and state types
class HelloInput(Input):
    name: str


class HelloState(State):
    greeting: str
    message: str


# Define an activity for side effects
@loom.activity(name="format_greeting", retry_count=3, timeout_seconds=10)
async def format_greeting(name: str) -> str:
    """Format a personalized greeting."""
    await asyncio.sleep(0.1)  # Simulate some work
    return f"Hello, {name}! Welcome to Loom."


@loom.workflow(name="HelloWorkflow", version="1.0.0")
class HelloWorkflow(loom.Workflow[HelloInput, HelloState]):
    """A simple greeting workflow."""

    @loom.step(name="create_greeting")
    async def create_greeting(self, ctx: loom.WorkflowContext[HelloInput, HelloState]):
        """Generate a greeting using an activity."""
        # Execute activity (handles retries and timeouts)
        greeting = await ctx.activity(format_greeting, ctx.input["name"])

        # Update workflow state (emits STATE_SET event)
        await ctx.state.set("greeting", greeting)

        ctx.logger.info(f"Generated greeting: {greeting}")

    @loom.step(name="create_message")
    async def create_message(self, ctx: loom.WorkflowContext[HelloInput, HelloState]):
        """Create a farewell message."""
        message = f"Goodbye from {ctx.input['name']}!"
        await ctx.state.set("message", message)

        ctx.logger.info(f"Created message: {message}")
