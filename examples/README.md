# Loom Examples

This directory contains comprehensive examples demonstrating Loom's workflow orchestration capabilities.

## Usage

All examples use the published API with `import loom`:

```python
import loom

@loom.activity(name="my_activity", retry_count=3)
async def my_activity(param: str) -> str:
    return f"Result: {param}"

@loom.workflow(name="MyWorkflow", version="1.0.0")
class MyWorkflow(loom.Workflow[InputType, StateType]):
    @loom.step(name="step1")
    async def step1(self, ctx: loom.WorkflowContext[InputType, StateType]):
        result = await ctx.activity(my_activity, "value")
        await ctx.state.set("result", result)
```

## Available Examples

### 01_hello_workflow.py
Basic workflow demonstrating core concepts with simple activity execution.

```bash
python examples/01_hello_workflow.py
```

### 02_order_processing.py
Real-world order processing workflow with payment, inventory, and shipping.

```bash
python examples/02_order_processing.py
```

## CLI Usage

After installation, use the `loom` command:

```bash
# Initialize database
loom init

# Start distributed worker
loom worker --workers 4

# List all workflows
loom list

# Inspect specific workflow
loom inspect <workflow-id>

# View statistics
loom stats
```

## Installation

Install the package in development mode:

```bash
pip install -e .
```

Or install from PyPI (when published):

```bash
pip install loom-core
```
