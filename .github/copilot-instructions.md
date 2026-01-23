# Loom — Final Design & Implementation Document (Typed Edition)

*A Deterministic, Durable, Typed Workflow Orchestration Library for Python*

> **This version updates the Loom design to include strong typing using `typing.Generic`,
> so both humans and Copilot can reason about workflow state, inputs, and ctx correctly.**

---

## 1. Purpose & Scope

**Loom** is a **Temporal-inspired workflow orchestration library** for Python with:

* Deterministic, replay-driven workflows
* Durable async execution
* SQLite-based portability
* Clear separation of orchestration vs side effects
* **First-class static typing support**

This document is the **canonical reference** for implementing Loom.

---

## 2. Core Design Principles

1. Determinism over convenience
2. Replay is execution
3. One workflow step at a time
4. Side effects only via activities
5. DB is memory + transport
6. **Types describe workflow contracts**

---

## 3. Typed Mental Model (Important)

Loom workflows are parameterized by:

* **Input type** – immutable
* **State type** – mutable but deterministic

```python
Workflow[Input, State]
```

This allows:

* Safer refactors
* Copilot correctness
* IDE autocompletion
* Clear contracts

---

## 4. Public User API (Typed)

---

## 4.1 Workflow Definition (Typed)

```python
from dataclasses import dataclass
import loom

@dataclass
class AssessmentInput:
    assessment_id: str

@dataclass
class AssessmentState:
    sent: bool = False
    submission: dict | None = None
    result: dict | None = None


@loom.workflow
class AssessmentWorkflow(
    loom.Workflow[AssessmentInput, AssessmentState]
):

    @loom.step
    async def send(self, ctx: loom.WorkflowContext[AssessmentState]):
        await ctx.activity(send_assessment, ctx.input.assessment_id)
        ctx.state.sent = True

    @loom.step
    async def wait(self, ctx: loom.WorkflowContext[AssessmentState]):
        await ctx.sleep(48 * 3600)

    @loom.step
    async def collect(self, ctx: loom.WorkflowContext[AssessmentState]):
        ctx.state.submission = await ctx.activity(
            fetch_submission,
            ctx.input.assessment_id
        )

    @loom.step
    async def validate(self, ctx: loom.WorkflowContext[AssessmentState]):
        ctx.state.result = await ctx.activity(
            run_validation_agent,
            ctx.state.submission
        )
```

---

## 5. Generic Types (Core)

### 5.1 Workflow Base Class

```python
class Workflow(Generic[InputT, StateT]):
    ...
```

* `InputT` → immutable input
* `StateT` → deterministic state

---

### 5.2 WorkflowContext (Typed)

```python
class WorkflowContext(Generic[StateT]):
    workflow_id: str
    input: Any
    state: StateT
```

Used as:

```python
ctx: WorkflowContext[AssessmentState]
```

---

## 6. Compile / Execute / Start (Typed Semantics)

### 6.1 Compile

```python
wf = AssessmentWorkflow.compile()
```

Returns:

```python
CompiledWorkflow[AssessmentInput, AssessmentState]
```

Responsibilities:

* Freeze structure
* Validate steps
* Compute source hash
* Cache definition

---

### 6.2 Execute (Local, Typed)

```python
result_state: AssessmentState = await wf.execute(
    AssessmentInput(assessment_id="A1")
)
```

Characteristics:

* No DB
* No replay
* No workers
* Direct async execution
* Type-safe state access

---

### 6.3 Start (Durable, Typed)

```python
handle = await wf.start(
    AssessmentInput(assessment_id="A1")
)
```

Returns:

```python
WorkflowHandle[AssessmentState]
```

---

## 7. WorkflowHandle (Typed)

```python
class WorkflowHandle(Generic[StateT]):
    id: str

    async def status(self) -> WorkflowStatus: ...
    async def result(self) -> StateT: ...
    async def signal(self, name: str, **payload) -> None: ...
```

---

## 8. WorkflowContext API (Typed, Final)

### 8.1 Execution APIs

```python
await ctx.activity(fn, *args, **kwargs)
await ctx.sleep(seconds: int)
await ctx.wait_for_signal(name: str) -> dict
await ctx.start_workflow(
    WorkflowCls,
    input: InputT
)
```

---

### 8.2 State Access (Strongly Typed)

```python
ctx.state.sent = True
ctx.state.submission = submission
```

Rules:

* State must be JSON-serializable
* Mutations are persisted as events
* State is rebuilt during replay

---

### 8.3 What ctx Must NOT Expose

❌ DB access
❌ system clock
❌ randomness
❌ filesystem
❌ network

This enforces determinism.

---

## 9. Activities (Typed Side Effects)

### 9.1 Definition

```python
@loom.activity(retry=3, timeout=30)
async def fetch_submission(assessment_id: str) -> dict:
    ...
```

Activities:

* Can be fully typed
* Return values are persisted
* Are replay-safe

---

### 9.2 ctx.activity Typing

```python
T = TypeVar("T")

async def activity(
    self,
    fn: Callable[..., Awaitable[T]],
    *args
) -> T
```

Copilot understands return types correctly.

---

## 10. Execution & Replay (Typed Flow)

* Workflow code always re-runs from step 1
* Completed steps are skipped
* Activity results are loaded from history
* State is reconstructed deterministically

Types are **compile-time only**; runtime behavior is unchanged.

---

## 11. Scheduling & Time

### 11.1 Typed Sleep

```python
await ctx.sleep(3600)
```

Persists:

```json
{ "type": "TIMER_SCHEDULED", "fire_at": "..." }
```

---

## 12. Signals (Typed Payloads)

```python
await handle.signal(
    "approve",
    reviewer_id="U1"
)
```

Workflow side:

```python
signal: dict = await ctx.wait_for_signal("approve")
```

(You may later introduce `TypedSignal[T]`.)

---

## 13. Parallelism Rules (Unchanged)

| Level                 | Parallel |
| --------------------- | -------- |
| Workflow instances    | ✅        |
| Activities            | ✅        |
| Steps (same workflow) | ❌        |

Typing does **not** affect concurrency semantics.

---

## 14. Database Schema (Unchanged)

### workflows

```sql
id TEXT PRIMARY KEY
name TEXT
status TEXT
created_at
```

### events (append-only)

```sql
id INTEGER PRIMARY KEY AUTOINCREMENT
workflow_id TEXT
type TEXT
payload JSON
created_at
```

### tasks

```sql
id TEXT PRIMARY KEY
workflow_id TEXT
kind TEXT
target TEXT
run_at TIMESTAMP
status TEXT
```

---

## 15. Failure & Recovery (Typed Safety)

* Worker crashes do not corrupt state
* Activity retries preserve types
* Replay restores state accurately

---

## 16. Non-Goals (v1)

* Parallel steps inside a workflow
* In-memory-only execution
* Cross-workflow shared state
* Typed signal schemas (v2)

---

## 17. Final Typed Mental Model

```
Workflow[Input, State]  → deterministic logic
WorkflowContext[State] → controlled execution boundary
Activity[T]            → side effects + data transport
SQLite                 → memory + transport
Replay                 → execution engine
```

---

## 18. Final Notes

This typed design gives you:

* Temporal-grade correctness
* Python-native ergonomics
* IDE + Copilot intelligence
* Future-safe refactoring
