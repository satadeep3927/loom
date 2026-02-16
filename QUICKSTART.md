# Quick Start Guide

This guide helps you get a workflow running with Loom in a few minutes.

## 1. Install and Initialize

```bash
# From a virtualenv, install the project in editable mode
pip install -e .

# Or, from PyPI once installed there
# pip install loom-core

# Initialize the SQLite database and run migrations
loom init
```

This will create `workflows.db` in the current directory.

## 2. Your First Workflow

Create a file `my_first_workflow.py` in the project root:

```python
import asyncio
import loom
from loom.schemas.state import Input, State


# 1. Define your input and state types
class HelloInput(Input):
    name: str


class HelloState(State):
    greeting: str | None


# 2. Define an activity (for side effects)
@loom.activity(name="get_greeting", retry_count=3, timeout_seconds=10)
async def get_greeting(name: str) -> str:
    return f"Hello, {name}! Welcome to Loom."


# 3. Define your workflow
@loom.workflow(name="HelloWorkflow", version="1.0.0")
class HelloWorkflow(loom.Workflow[HelloInput, HelloState]):

    @loom.step(name="greet")
    async def greet_step(self, ctx: loom.WorkflowContext[HelloInput, HelloState]):
        # Call activity (durable, retryable)
        greeting = await ctx.activity(get_greeting, ctx.input["name"])

        # Update durable state (emits STATE_SET event)
        await ctx.state.set("greeting", greeting)

        # Replay-safe logging
        ctx.logger.info(f"Generated greeting: {greeting}")


# 4. Start the workflow
async def main() -> None:
    handle = await HelloWorkflow.start({"name": "World"})

    print(f"Workflow started: {handle.workflow_id}")
    final_state = await handle.result()
    print(f"Final state: {final_state}")


if __name__ == "__main__":
    asyncio.run(main())
```

## 3. Run the Worker

In a separate terminal from the project root:

```bash
loom worker --workers 4
```

The worker process will continuously poll the database for new tasks and execute
your workflow steps.

## 4. Execute Your Workflow Script

Back in the first terminal, run:

```bash
python my_first_workflow.py
```

You should see the workflow ID and the final state printed.

## 5. Inspect Workflows

Use the CLI to inspect what happened:

```bash
# List recent workflows
loom list

# Inspect a specific workflow (optionally with events)
loom inspect <workflow-id> --events

# Show database statistics
loom stats
```

## 6. Next Steps

- Read the main README for architecture details and advanced concepts.
- Explore the examples in `examples/` for more complex workflows.
- Run tests with `pytest`.

Happy workflow orchestrating! 🧵
