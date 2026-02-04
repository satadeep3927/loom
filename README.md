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

**Note**: For state updates, use:
- `await ctx.state.set("key", value)` for single values
- `await ctx.state.update(key=lambda _: asyncio.sleep(0, value))` for batch updates (requires awaitable)

See [STATE_MANAGEMENT.md](STATE_MANAGEMENT.md) for detailed examples.

### Start a Workflow

```python
async def main():
    db = loom.Database()
    async with db:
        # Initialize database
        await db.migrate_up()
        
        # Start workflow
        handle = await db.start_workflow(
            OrderWorkflow,
            workflow_input=OrderInput(
                order_id="ORD-12345",
                customer_email="customer@example.com"
            ),
            initial_state=OrderState(
                payment_confirmed=False,
                email_sent=False
            ),
        )
        
        print(f"Workflow started: {handle.workflow_id}")
        
        # Execute workflow tasks
        while True:
            task_executed = await loom.run_once()
            if not task_executed:
                break


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
