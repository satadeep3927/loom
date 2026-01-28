# Loom - Durable Workflow Orchestration 🧵

[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A Python-based durable workflow orchestration engine inspired by [Temporal](https://temporal.io/) and [Durable Task Framework](https://github.com/Azure/durabletask). Loom provides event-sourced, deterministic workflow execution with automatic recovery and replay capabilities.

## ✨ Features

- 🔄 **Event Sourcing**: All workflow state changes persisted as immutable events
- 🎯 **Deterministic Replay**: Workflows reconstruct from event history for recovery
- 🔧 **Type Safe**: Full generic typing support with `Workflow[InputT, StateT]`
- ⚡ **Async First**: Built on asyncio for high-performance concurrent execution
- 🛡️ **Durable Execution**: Workflows survive process crashes and auto-recover
- 🎨 **Beautiful CLI**: Rich console interface with progress tracking
- 🧪 **Well Tested**: Comprehensive test suite with pytest

## 🚀 Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/loom.git
cd loom

# Install dependencies
pip install -r requirements.txt

# Initialize database
python loom_cli.py init
```

### Define a Workflow

```python
from dataclasses import dataclass
from datetime import timedelta

from src.core.context import WorkflowContext
from src.core.workflow import Workflow
from src.decorators.workflow import workflow, step
from src.decorators.activity import activity


# Define your data types
@dataclass
class OrderInput:
    order_id: str
    customer_email: str


@dataclass
class OrderState:
    payment_confirmed: bool = False
    email_sent: bool = False


# Define activities (side effects)
@activity(name="process_payment", retry_count=3, timeout_seconds=30)
async def process_payment(order_id: str) -> bool:
    # Call payment API
    return True


@activity(name="send_email", retry_count=2)
async def send_confirmation_email(email: str, order_id: str) -> None:
    # Send email via service
    pass


# Define workflow
@workflow(name="OrderProcessing", version="1.0.0")
class OrderWorkflow(Workflow[OrderInput, OrderState]):
    
    @step(name="process_payment")
    async def payment_step(self, ctx: WorkflowContext[OrderInput, OrderState]):
        success = await ctx.activity(process_payment, ctx.input.order_id)
        await ctx.state.set("payment_confirmed", success)
        ctx.logger.info(f"Payment processed: {success}")
    
    @step(name="send_confirmation")
    async def notification_step(self, ctx: WorkflowContext[OrderInput, OrderState]):
        if ctx.state.get("payment_confirmed"):
            await ctx.activity(
                send_confirmation_email,
                ctx.input.customer_email,
                ctx.input.order_id
            )
            await ctx.state.set("email_sent", True)
            ctx.logger.info("Confirmation email sent")
```

### Start a Workflow

```python
import asyncio

async def main():
    # Compile workflow
    workflow = OrderWorkflow.compile()
    
    # Start execution
    handle = await workflow.start(
        input=OrderInput(
            order_id="ORD-12345",
            customer_email="customer@example.com"
        )
    )
    
    print(f"Workflow started: {handle.id}")
    
    # Check status
    status = await handle.status()
    print(f"Status: {status}")

asyncio.run(main())
```

### Run the Worker

```bash
# Start worker with 4 concurrent task processors
python loom_cli.py worker

# Custom configuration
python loom_cli.py worker --workers 8 --poll-interval 1.0
```

## 🎛️ CLI Commands

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

```
┌─────────────────────────────────────────────────────────┐
│                      Workflow                           │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐             │
│  │  Step 1  │→ │  Step 2  │→ │  Step 3  │             │
│  └──────────┘  └──────────┘  └──────────┘             │
└─────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────┐
│                  WorkflowContext                        │
│  • State Management (StateProxy)                        │
│  • Activity Execution                                   │
│  • Event Replay & Cursor                                │
│  • Logger (replay-safe)                                 │
└─────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────┐
│                      Engine                             │
│  • replay_until_block() - Step execution                │
│  • replay_activity() - Activity retry                   │
│  • Event matching & determinism                         │
└─────────────────────────────────────────────────────────┘
                        ↓
┌─────────────────────────────────────────────────────────┐
│                    Database (SQLite)                    │
│  • workflows   • events   • tasks   • logs              │
└─────────────────────────────────────────────────────────┘
```

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

## 📚 Documentation

See [`.copilot-instructions.md`](.copilot-instructions.md) for comprehensive development guidelines including:

- Event sourcing patterns
- Deterministic execution rules
- Activity best practices
- Testing strategies
- Common pitfalls to avoid

## 🧪 Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src --cov-report=html

# Run specific test file
pytest tests/test_workflow.py

# Verbose output
pytest -v
```

## 📂 Project Structure

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
├── loom_cli.py         # CLI interface
└── requirements.txt    # Dependencies
```

## 🔧 Configuration

Loom uses SQLite by default for simplicity. For production:

- Consider PostgreSQL/MySQL for scalability
- Implement connection pooling
- Add monitoring and alerting
- Deploy multiple workers for high availability

## 🤝 Contributing

Contributions welcome! Please ensure:

1. Tests pass: `pytest`
2. Code formatted: `black .`
3. Type checking: `mypy src`
4. Linting: `ruff check src`

## 📝 License

MIT License - see LICENSE file for details

## 🙏 Acknowledgments

Inspired by:
- [Temporal](https://temporal.io/) - The workflow orchestration platform
- [Durable Task Framework](https://github.com/Azure/durabletask) - Microsoft's durable task library
- [Cadence](https://cadenceworkflow.io/) - Uber's workflow platform

## 📧 Contact

For questions and support, please open an issue on GitHub.

---

**Built with ❤️ using Python 3.12+**
