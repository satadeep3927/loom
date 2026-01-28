# Quick Start Guide

This guide will help you get started with Loom in 5 minutes.

## Installation

```bash
# Install dependencies
pip install -r requirements.txt

# Initialize the database
python loom_cli.py init
```

## Your First Workflow

Create a file `my_first_workflow.py`:

```python
from dataclasses import dataclass
from src.core.context import WorkflowContext
from src.core.workflow import Workflow
from src.decorators.workflow import workflow, step
from src.decorators.activity import activity


# 1. Define your data types
@dataclass
class HelloInput:
    name: str


@dataclass
class HelloState:
    greeting: str = ""


# 2. Define an activity (for side effects)
@activity(name="get_greeting")
async def get_greeting(name: str) -> str:
    return f"Hello, {name}!"


# 3. Define your workflow
@workflow(name="HelloWorkflow", version="1.0.0")
class HelloWorkflow(Workflow[HelloInput, HelloState]):
    
    @step(name="greet")
    async def greet_step(self, ctx: WorkflowContext[HelloInput, HelloState]):
        # Call activity
        greeting = await ctx.activity(get_greeting, ctx.input.name)
        
        # Update state
        await ctx.state.set("greeting", greeting)
        
        # Log
        ctx.logger.info(f"Generated greeting: {greeting}")


# 4. Start the workflow
async def main():
    import asyncio
    
    workflow = HelloWorkflow.compile()
    handle = await workflow.start(input=HelloInput(name="World"))
    
    print(f"Workflow started: {handle.id}")
    print(f"Status: {await handle.status()}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
```

## Run the Worker

In a separate terminal:

```bash
python loom_cli.py worker
```

## Execute Your Workflow

```bash
python my_first_workflow.py
```

## Check Workflow Status

```bash
# List all workflows
python loom_cli.py list

# Inspect specific workflow
python loom_cli.py inspect <workflow-id>

# Show database stats
python loom_cli.py stats
```

## Next Steps

- Read the [README.md](README.md) for architecture details
- Check [examples/](examples/) for more complex workflows
- Review [.copilot-instructions.md](.copilot-instructions.md) for best practices
- Run tests: `pytest`

## Common Patterns

### Retry Failed Activities

```python
@activity(name="api_call", retry_count=3, timeout_seconds=30)
async def call_external_api(url: str) -> dict:
    # This will retry up to 3 times on failure
    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        response.raise_for_status()
        return response.json()
```

### Sleep/Delay in Workflows

```python
from datetime import timedelta

@step()
async def delayed_step(self, ctx: WorkflowContext):
    # Sleep for 5 minutes (durable - survives process restart)
    await ctx.sleep(timedelta(minutes=5))
    ctx.logger.info("Woke up after 5 minutes!")
```

### Update Multiple State Fields

```python
@step()
async def batch_update(self, ctx: WorkflowContext):
    await ctx.state.update({
        "processed": True,
        "count": 42,
        "timestamp": "2024-01-28T10:00:00Z"
    })
```

Happy workflow orchestrating! 🧵
