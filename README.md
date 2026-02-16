# Loom - Durable Workflow Orchestration

<p align="center">
  <img src="https://raw.githubusercontent.com/satadeep3927/loom/refs/heads/main/docs/logo-white.png" alt="Loom Logo" width="200"/>
</p>

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![PyPI](https://img.shields.io/badge/pypi-loom--core-blue)](https://pypi.org/project/loom-core/)

A Python-based durable workflow orchestration engine inspired by [Temporal](https://temporal.io/) and [Durable Task Framework](https://github.com/Azure/durabletask). Loom provides event-sourced, deterministic workflow execution with automatic recovery and replay capabilities.

## Features

- **Event Sourcing**: All workflow state changes persisted as immutable events
- **Deterministic Replay**: Workflows reconstruct from event history for recovery
- **Type Safe**: Full generic typing support with `Workflow[InputT, StateT]`
- **Async First**: Built on asyncio for high-performance concurrent execution
- **Durable Execution**: Workflows survive process crashes and auto-recover
- **Beautiful CLI**: Rich console interface with progress tracking
- **Well Tested**: Comprehensive test suite with pytest

## Quick Start

### Installation

```bash
pip install loom-core
```

Or install from source:

```bash
git clone https://github.com/satadeep3927/loom.git
cd loom
pip install -e .
```

### Define a Workflow

```python
import asyncio
from typing import TypedDict
import loom


# Define your data types
class OrderInput(TypedDict):
    order_id: str
    customer_email: str


class OrderState(TypedDict):
    payment_confirmed: bool
    email_sent: bool


# Define activities (side effects)
@loom.activity(name="process_payment", retry_count=3, timeout_seconds=30)
async def process_payment(order_id: str) -> bool:
    # Call payment API
    return True


@loom.activity(name="send_email", retry_count=2)
async def send_confirmation_email(email: str, order_id: str) -> None:
    # Send email via service
    pass


# Define workflow
@loom.workflow(name="OrderProcessing", version="1.0.0")
class OrderWorkflow(loom.Workflow[OrderInput, OrderState]):
    
    @loom.step(name="process_payment")
    async def payment_step(self, ctx: loom.WorkflowContext[OrderInput, OrderState]):
        success = await ctx.activity(process_payment, ctx.input["order_id"])
        await ctx.state.set("payment_confirmed", success)
        ctx.logger.info(f"Payment processed: {success}")
    
    @loom.step(name="send_confirmation")
    async def notification_step(self, ctx: loom.WorkflowContext[OrderInput, OrderState]):
        if ctx.state["payment_confirmed"]:
            await ctx.activity(
                send_confirmation_email,
                ctx.input["customer_email"],
                ctx.input["order_id"]
            )
            await ctx.state.set("email_sent", True)
            ctx.logger.info("Confirmation email sent")
```

### Start a Workflow

The simplest way to start a workflow is using the class method:

```python
import asyncio
import loom


async def main():
    # Start workflow using the class method (recommended)
    handle = await OrderWorkflow.start(
        OrderInput(
            order_id="ORD-12345",
            customer_email="customer@example.com",
        )
    )

    print(f"Workflow started: {handle.workflow_id}")

    # Wait for completion and get result (final state)
    result = await handle.result()
    print(f"Workflow completed with state: {result}")


if __name__ == "__main__":
    asyncio.run(main())
```

### Run the Worker

```bash
# Initialize database
loom init

# Start worker with 4 concurrent task processors
loom worker

# Custom configuration
loom worker --workers 8 --poll-interval 1.0
```

### 🌐 Web Dashboard

Start the interactive web dashboard to monitor and manage workflows in real-time:

```bash
# Start web server on default port (8000)
loom web

# Custom host and port
loom web --host 0.0.0.0 --port 3000

# Development mode with auto-reload
loom web --reload
```

**Access the dashboard at `http://localhost:8000`** after starting the server.

The web dashboard provides:
- 📊 **Real-time workflow monitoring** with Server-Sent Events (SSE)
- 📈 **Workflow definition graphs** (similar to Airflow DAGs) showing workflow structure
- 📋 **Task queue visualization** and execution tracking
- 📜 **Event history** with comprehensive audit trails
- 📊 **Performance metrics** and system statistics
- 📚 **Interactive API documentation** at `/docs`

## 🎯 Complete Example

Here's a complete workflow example demonstrating all features:

```python
import random
from datetime import timedelta
import loom
from loom.core.context import WorkflowContext
from loom.core.workflow import Workflow
from loom.schemas.state import Input, State


class QuizInput(Input):
    lesson_id: str


class QuizState(State):
    quiz_id: str | None
    wait_time: int | None
    submissions: list | None
    result: dict | None


@loom.activity(name="GenerateQuiz")
async def generate_quiz_activity() -> str:
    quiz_id = f"Quiz-{random.randint(1000, 9999)}"
    print(f"Generated Quiz: {quiz_id}")
    return quiz_id


@loom.activity(name="SendQuizToLMS")
async def send_quiz_to_lms_activity(quiz_id: str) -> None:
    print(f"Sent {quiz_id} to LMS")


@loom.activity(name="FetchWaitTime")
async def fetch_wait_time_activity() -> int:
    return 120  # 2 minutes


@loom.activity(name="PullSubmissions")
async def pull_submissions_activity(quiz_id: str) -> list:
    print(f"Pulled submissions for {quiz_id}")
    return ["Submission 1", "Submission 2", "Submission 3"]


@loom.activity(name="AssessResult")
async def assess_result_activity(quiz_id: str) -> dict:
    score = random.randint(50, 100)
    return {"quiz_id": quiz_id, "score": score, "status": "Completed"}


@loom.activity(name="StoreResult")
async def store_result_activity(result: dict) -> None:
    print(f"Stored Result: {result}")


@loom.workflow(
    name="AssessmentWorkflow",
    version="1.0.0",
    description="A workflow for Quiz management."
)
class AssessmentWorkflow(Workflow[QuizInput, QuizState]):

    @loom.step(name="generate_quiz")
    async def generate_quiz(self, ctx: WorkflowContext[QuizInput, QuizState]):
        ctx.logger.info("Generating Quiz...")
        quiz_id = await ctx.activity(generate_quiz_activity)
        await ctx.state.set("quiz_id", quiz_id)

    @loom.step(name="send_to_lms")
    async def send_to_lms(self, ctx: WorkflowContext[QuizInput, QuizState]):
        quiz_id = ctx.state.get("quiz_id")
        ctx.logger.info(f"Sending Quiz {quiz_id} to LMS...")
        await ctx.activity(send_quiz_to_lms_activity, quiz_id)

    @loom.step(name="fetch_wait_time")
    async def fetch_wait_time(self, ctx: WorkflowContext[QuizInput, QuizState]):
        ctx.logger.info("Fetching wait time...")
        wait_time = await ctx.activity(fetch_wait_time_activity)
        await ctx.state.set("wait_time", wait_time)

    @loom.step(name="wait_step")
    async def wait_step(self, ctx: WorkflowContext[QuizInput, QuizState]):
        wait_time = ctx.state.get("wait_time")
        ctx.logger.info(f"Waiting for {wait_time} seconds...")
        await ctx.sleep(delta=timedelta(seconds=wait_time))

    @loom.step(name="pull_submissions")
    async def pull_submissions(self, ctx: WorkflowContext[QuizInput, QuizState]):
        quiz_id = ctx.state.get("quiz_id")
        submissions = await ctx.activity(pull_submissions_activity, quiz_id)
        await ctx.state.set("submissions", submissions)

    @loom.step(name="assess_result")
    async def assess_result(self, ctx: WorkflowContext[QuizInput, QuizState]):
        quiz_id = ctx.state.get("quiz_id")
        result = await ctx.activity(assess_result_activity, quiz_id)
        await ctx.state.set("result", result)

    @loom.step(name="store_result")
    async def store_result(self, ctx: WorkflowContext[QuizInput, QuizState]):
        result = ctx.state.get("result")
        await ctx.activity(store_result_activity, result)
        ctx.logger.info("Workflow completed!")


# Start the workflow
async def main():
    handle = await AssessmentWorkflow.start({"lesson_id": "lesson_123"})
    result = await handle.status()
    print(f"Workflow Status: {result}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
```

This example demonstrates:
- **Multiple steps** with sequential execution
- **Activity calls** for side effects
- **State management** across workflow execution
- **Timer/sleep** operations for waiting
- **Logging** with workflow context
- **Type safety** with generic workflow types

## 📚 Core Concepts

### State Management

Loom provides three ways to manage workflow state, all of which are durable and replay-safe:

#### 1. Single Key Updates (`set`)

Use `ctx.state.set()` for individual state changes. Each call emits a `STATE_SET` event:

```python
@loom.step()
async def process_order(self, ctx: loom.WorkflowContext[OrderInput, OrderState]):
    # Set individual keys
    await ctx.state.set("order_id", "ORD-123")
    await ctx.state.set("status", "processing")
    await ctx.state.set("timestamp", "2024-01-15T10:30:00")
    
    # Read state
    order_id = ctx.state["order_id"]  # Dictionary access
    status = ctx.state.get("status")  # Safe get
    items = ctx.state.get("items", [])  # With default
```

#### 2. Batch Updates (`update`)

Use `ctx.state.update()` to replace the entire state atomically. Emits a single `STATE_UPDATE` event:

```python
@loom.step()
async def update_order_state(self, ctx: loom.WorkflowContext[OrderInput, OrderState]):
    # Update entire state with a function that receives current state
    await ctx.state.update(lambda state: {
        **state,  # Preserve existing keys
        "order_id": "ORD-123",
        "status": "shipped",
        "shipped_at": "2024-01-15T14:00:00"
    })
```

**Important**: The update function receives the current state and must return the complete new state.

#### 3. Batch Context Manager (`batch`)

Use `async with ctx.state.batch()` to collect multiple `set()` calls into a single `STATE_UPDATE` event:

```python
@loom.step()
async def batch_update(self, ctx: loom.WorkflowContext[OrderInput, OrderState]):
    # Multiple updates batched into single STATE_UPDATE event
    async with ctx.state.batch():
        await ctx.state.set("order_id", "ORD-123")
        await ctx.state.set("status", "processing")
        await ctx.state.set("items", ["item1", "item2"])
        await ctx.state.set("total", 99.99)
    # Single STATE_UPDATE event emitted when context exits
```

**When to use each**:
- `set()`: Simple, single updates
- `update()`: Replace entire state based on current values
- `batch()`: Multiple related updates that should be atomic

### Workflow Handles

Workflow handles provide control and monitoring of running workflows:

```python
# Start workflow and get handle
handle = await OrderWorkflow.start({"order_id": "ORD-123"})

# Get workflow ID
print(f"Workflow ID: {handle.workflow_id}")

# Check status (returns "RUNNING", "COMPLETED", "FAILED", etc.)
status = await handle.status()
print(f"Status: {status}")

# Wait for completion and get final state
try:
    result = await handle.result()
    print(f"Completed with state: {result}")
except loom.WorkflowExecutionError as e:
    print(f"Workflow failed: {e}")
except loom.ActivityFailedError as e:
    print(f"Activity '{e.activity_name}' failed: {e.error_message}")

# Send signals to running workflow
await handle.signal("approve", {"approved_by": "admin", "timestamp": "2024-01-15"})

# Cancel workflow
await handle.cancel(reason="User requested cancellation")
```

### Exception Handling

⚠️ **CRITICAL**: Never catch `StopReplay` in your workflow code!

`StopReplay` is an internal control flow exception used by Loom to pause workflow replay when waiting for activities, timers, or signals. Catching it will break workflow execution and recovery.

```python
# ❌ WRONG - This will break workflow execution!
@loom.step()
async def bad_step(self, ctx):
    try:
        await ctx.activity(my_activity)
    except Exception:  # This catches StopReplay!
        ctx.logger.error("Error occurred")  # Workflow breaks here
        pass

# ❌ ALSO WRONG
@loom.step()
async def another_bad_step(self, ctx):
    try:
        await ctx.activity(my_activity)
    except:  # Never use bare except
        pass

# ✅ CORRECT - Catch specific exceptions only
@loom.step()
async def good_step(self, ctx):
    try:
        result = await ctx.activity(my_activity)
        await ctx.state.set("result", result)
    except loom.ActivityFailedError as e:
        # Handle activity failure
        ctx.logger.error(f"Activity failed: {e}")
        await ctx.state.set("error", str(e))
        # Workflow can continue or raise to fail
```

**Available Exceptions**:

Use these in your application code (not inside workflow steps):

```python
import loom

# Workflow execution
try:
    handle = await MyWorkflow.start(input_data, state)
    result = await handle.result()
except loom.WorkflowNotFoundError:
    print("Workflow doesn't exist")
except loom.WorkflowStillRunningError:
    print("Workflow hasn't completed yet")
except loom.WorkflowExecutionError:
    print("Workflow failed during execution")
except loom.ActivityFailedError as e:
    print(f"Activity '{e.activity_name}' failed: {e.error_message}")
except loom.NonDeterministicWorkflowError:
    print("Workflow code changed in incompatible way")
```

**Why is StopReplay special?**

`StopReplay` is raised internally when the workflow execution reaches a point where it needs to wait for external events:
- An activity that hasn't completed yet
- A timer that hasn't fired
- A signal that hasn't been received

The engine catches this exception to save progress and pause execution. If your code catches it, the engine never receives it, and the workflow cannot properly pause and resume.

### Best Practices

#### ✅ Do:

- **Use activities for side effects**: All API calls, database writes, file I/O, etc.
  ```python
  @loom.activity(name="send_email", retry_count=3)
  async def send_email(to: str, subject: str) -> bool:
      # API call, retry on failure
      await email_service.send(to, subject)
      return True
  ```

- **Make activities idempotent**: Safe to retry multiple times
  ```python
  @loom.activity(name="create_order")
  async def create_order(order_id: str) -> dict:
      # Check if order exists first (idempotent)
      existing = await db.get_order(order_id)
      if existing:
          return existing
      return await db.create_order(order_id)
  ```

- **Use batch for related updates**: More efficient, single event
  ```python
  async with ctx.state.batch():
      await ctx.state.set("step", 3)
      await ctx.state.set("progress", 75)
      await ctx.state.set("updated_at", timestamp)
  ```

- **Use type hints**: Better IDE support and type checking
  ```python
  class MyWorkflow(loom.Workflow[MyInput, MyState]):
      @loom.step()
      async def my_step(self, ctx: loom.WorkflowContext[MyInput, MyState]):
          # ctx.input is MyInput, ctx.state is MyState
          pass
  ```

- **Log with ctx.logger**: Respects replay mode, won't duplicate logs
  ```python
  ctx.logger.info("Processing order")  # Only logs during actual execution
  ctx.logger.error("Failed to process")  # Not during replay
  ```

- **Catch specific exceptions**: Only catch what you can handle
  ```python
  try:
      await ctx.activity(risky_activity)
  except loom.ActivityFailedError:
      # Handle specific failure
      pass
  ```

#### ❌ Don't:

- **Don't use random in workflows**: Breaks determinism
  ```python
  # ❌ WRONG
  @loom.step()
  async def bad_step(self, ctx):
      value = random.randint(1, 100)  # Different on replay!
      await ctx.state.set("value", value)
  
  # ✅ CORRECT - Use activity
  @loom.activity(name="generate_random")
  async def generate_random() -> int:
      return random.randint(1, 100)
  
  @loom.step()
  async def good_step(self, ctx):
      value = await ctx.activity(generate_random)
      await ctx.state.set("value", value)
  ```

- **Don't use datetime.now() in workflows**: Non-deterministic
  ```python
  # ❌ WRONG
  @loom.step()
  async def bad_step(self, ctx):
      now = datetime.now()  # Different on replay!
  
  # ✅ CORRECT - Use activity
  @loom.activity(name="get_timestamp")
  async def get_timestamp() -> str:
      return datetime.now().isoformat()
  ```

- **Don't perform I/O in workflows**: Use activities instead
  ```python
  # ❌ WRONG
  @loom.step()
  async def bad_step(self, ctx):
      data = await http_client.get("https://api.example.com")  # Don't!
  
  # ✅ CORRECT
  @loom.activity(name="fetch_data")
  async def fetch_data() -> dict:
      return await http_client.get("https://api.example.com")
  ```

- **Don't catch Exception or bare except**: Catches StopReplay
  ```python
  # ❌ WRONG
  try:
      await ctx.activity(my_activity)
  except Exception:  # Catches everything including StopReplay!
      pass
  
  # ✅ CORRECT
  try:
      await ctx.activity(my_activity)
  except loom.ActivityFailedError:  # Specific exception only
      pass
  ```

- **Don't modify state without ctx.state**: Won't be persisted
  ```python
  # ❌ WRONG
  @loom.step()
  async def bad_step(self, ctx):
      my_state = {"value": 123}
      # State not persisted!
  
  # ✅ CORRECT
  @loom.step()
  async def good_step(self, ctx):
      await ctx.state.set("value", 123)  # Persisted
  ```

## CLI Commands

```bash
# Initialize database
loom init

# Start distributed worker
loom worker [--workers 4] [--poll-interval 0.5]

# List workflows
loom list [--limit 50] [--status RUNNING]

# Inspect workflow details
loom inspect <workflow-id> [--events]

# Show database statistics
loom stats
```

## 🏗️ Architecture

### Core Components

![Architecture](https://raw.githubusercontent.com/satadeep3927/loom/refs/heads/main/docs/diagram.svg)

### Event Types

- `WORKFLOW_STARTED` - Workflow initialization
- `WORKFLOW_COMPLETED` - Successful completion
- `WORKFLOW_FAILED` - Fatal error occurred
- `STATE_SET` - Single state key updated
- `STATE_UPDATE` - Batch state update
- `ACTIVITY_SCHEDULED` - Activity queued for execution
- `ACTIVITY_COMPLETED` - Activity finished successfully
- `ACTIVITY_FAILED` - Activity permanently failed
- `TIMER_FIRED` - Sleep/delay completed
- `SIGNAL_RECEIVED` - External signal received


## Project Structure

```
loom/
├── src/
│   ├── common/         # Shared utilities
│   ├── core/           # Core engine (context, engine, runner, worker)
│   ├── database/       # Database layer
│   ├── decorators/     # @workflow, @step, @activity
│   ├── lib/            # Utilities and progress tracking
│   ├── migrations/     # Database migrations
│   └── schemas/        # Type definitions
├── tests/              # Test suite
├── examples/           # Example workflows
├── loom.py             # Main package interface
└── pyproject.toml      # Package configuration
```

## Configuration

Loom uses SQLite by default for simplicity. For production:

- Consider PostgreSQL/MySQL for scalability
- Implement connection pooling
- Add monitoring and alerting
- Deploy multiple workers for high availability

## Contributing

Contributions welcome! Please ensure:

1. Tests pass: `pytest`
2. Code formatted: `black .`
3. Type checking: `mypy .`
4. Linting: `ruff check .`

## 📝 License

MIT License - see LICENSE file for details

## 🙏 Acknowledgments

Inspired by:
- [Temporal](https://temporal.io/) - The workflow orchestration platform
- [Durable Task Framework](https://github.com/Azure/durabletask) - Microsoft's durable task library
- [Cadence](https://cadenceworkflow.io/) - Uber's workflow platform
[GitHub](https://github.com/satadeep3927/loom/issues)
## 📧 Contact

For questions and support, please open an issue on GitHub.

---

**Built with ❤️ using Python 3.12+**
