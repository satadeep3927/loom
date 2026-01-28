# Loom - Durable Workflow Orchestration

## Project Overview

Loom is a Python-based durable workflow orchestration engine inspired by Temporal and Durable Task Framework. It provides event-sourced, deterministic workflow execution with automatic recovery and replay capabilities.

## Core Concepts

### Architecture Principles

1. **Event Sourcing**: All workflow state changes are persisted as immutable events
2. **Deterministic Replay**: Workflows can be reconstructed from event history
3. **Separation of Concerns**: Workflow logic (deterministic) vs Activities (side effects)
4. **Durability**: Workflows survive process crashes and automatically recover

### Key Components

#### Workflows
- Defined using `@workflow` decorator
- Contain `@step` methods that execute sequentially
- Must be deterministic (no random values, no direct I/O)
- Use generic types: `Workflow[InputT, StateT]`

#### Activities
- Defined using `@activity` decorator
- Handle all side effects (API calls, database writes, file I/O)
- Support retry policies and timeouts
- Should be idempotent when possible

#### Context (`WorkflowContext`)
- Execution environment for workflow steps
- Provides: `ctx.activity()`, `ctx.sleep()`, `ctx.state`, `ctx.logger`
- Manages event replay and cursor position
- Enforces determinism through event matching

#### Engine
- `replay_until_block()`: Replays workflow from history until blocking operation
- `replay_activity()`: Re-executes activities with retry logic
- Uses `StopReplay` exception to halt at non-deterministic operations

#### Database
- SQLite-based persistence with aiosqlite
- Tables: `workflows`, `events`, `tasks`, `logs`
- Migration system in `src/migrations/`
- Task queue for asynchronous execution

### Type System

```python
# Workflows are generic over Input and State types
class MyWorkflow(Workflow[MyInput, MyState]):
    @step()
    async def my_step(self, ctx: WorkflowContext[MyInput, MyState]):
        # ctx.input is of type MyInput (immutable)
        # ctx.state is of type MyState (mutable)
        pass
```

## Code Modification Guidelines

### When Adding New Features

1. **Maintain Event Sourcing**: All state changes must emit events
2. **Preserve Determinism**: Workflow code must produce same events on replay
3. **Use Type Hints**: Leverage generics and type annotations throughout
4. **Follow Async Patterns**: All I/O operations should be async
5. **Add Migrations**: Database schema changes require up/down migrations

### Event Types

Current event types:
- `WORKFLOW_STARTED`: Workflow creation
- `WORKFLOW_COMPLETED`: Successful completion
- `WORKFLOW_FAILED`: Fatal error
- `STATE_SET`: Single state key update
- `STATE_UPDATE`: Batch state update
- `ACTIVITY_SCHEDULED`: Activity queued
- `ACTIVITY_COMPLETED`: Activity success
- `ACTIVITY_FAILED`: Activity permanent failure
- `TIMER_FIRED`: Sleep/delay completed
- `SIGNAL_RECEIVED`: External signal

### Adding New Event Types

1. Add to event schema in `src/schemas/events.py`
2. Update replay logic in `Engine` and `WorkflowContext`
3. Add event creation method in `Database`
4. Create migration if storing in database

### Activity Best Practices

```python
@activity(
    name="descriptive_name",
    retry_count=3,  # Retry up to 3 times
    timeout_seconds=30  # 30 second timeout
)
async def my_activity(param: str) -> ReturnType:
    # Should be idempotent - safe to retry
    # Should handle failures gracefully
    # Should use async I/O
    pass
```

### Workflow Best Practices

```python
@workflow(name="MyWorkflow", version="1.0.0")
class MyWorkflow(Workflow[MyInput, MyState]):
    @step(name="initialization")
    async def init_step(self, ctx: WorkflowContext[MyInput, MyState]):
        # Use ctx.activity() for side effects
        result = await ctx.activity(my_activity, ctx.input.param)
        
        # Update state (emits STATE_SET event)
        await ctx.state.set("result", result)
        
        # Log (respects replay mode)
        ctx.logger.info(f"Processed: {result}")
        
        # Sleep/delay (emits TIMER event)
        await ctx.sleep(timedelta(seconds=5))
```

### Testing Considerations

- Mock the database layer for unit tests
- Test replay behavior with different event sequences
- Verify idempotency of activities
- Test failure and retry scenarios
- Validate state reconstruction from events

### Common Pitfalls to Avoid

❌ **Don't** use random values in workflows (breaks determinism)
❌ **Don't** perform I/O directly in workflow steps (use activities)
❌ **Don't** use `datetime.now()` in workflows (use `ctx.sleep()`)
❌ **Don't** modify state without using `ctx.state` proxy
❌ **Don't** catch `StopReplay` exception (internal control flow)

✅ **Do** use activities for all side effects
✅ **Do** make activities idempotent
✅ **Do** use type hints throughout
✅ **Do** emit events for all state changes
✅ **Do** validate inputs at workflow boundaries

### File Organization

```
src/
├── common/          # Shared utilities and base classes
│   ├── activity.py  # Activity loader
│   ├── config.py    # Configuration
│   ├── errors.py    # Custom exceptions
│   └── workflow.py  # Workflow registry
├── core/            # Core engine components
│   ├── compiled.py  # CompiledWorkflow
│   ├── context.py   # WorkflowContext
│   ├── engine.py    # Replay engine
│   ├── handle.py    # WorkflowHandle
│   ├── logger.py    # WorkflowLogger
│   ├── runner.py    # Task runner
│   ├── state.py     # StateProxy
│   └── workflow.py  # Base Workflow class
├── database/        # Data persistence
│   └── db.py        # Database interface
├── decorators/      # Public API decorators
│   ├── activity.py  # @activity
│   └── workflow.py  # @workflow, @step
├── migrations/      # Database migrations
│   ├── up/         # Upgrade scripts
│   └── down/       # Downgrade scripts
└── schemas/         # Type definitions
    ├── activity.py
    ├── context.py
    ├── database.py
    ├── events.py
    ├── tasks.py
    └── workflow.py
```

### Performance Notes

- SQLite is sufficient for development/small scale
- Consider PostgreSQL/MySQL for production scale
- Task claiming uses `SELECT FOR UPDATE` (single worker currently)
- Activity execution is async but tasks are processed sequentially

### Debugging Tips

1. Check `workflows.db` for event history
2. Use `ctx.logger` for replay-safe logging
3. Inspect task queue state in `tasks` table
4. Review migration scripts when schema issues occur
5. Set log level to DEBUG for verbose output

## Dependencies

Core:
- `aiosqlite`: Async SQLite database
- Python 3.12+ (uses new type parameter syntax)

Development:
- `pytest`: Testing framework
- `mypy`: Static type checking
- `black`: Code formatting
- `ruff`: Linting

## Version History

This is an active development project. Always maintain backward compatibility for:
- Event schemas (old workflows must replay)
- Database schema (migrations required)
- Public API (@workflow, @activity, @step decorators)
