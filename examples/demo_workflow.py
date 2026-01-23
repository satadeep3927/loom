from typing import TypedDict

from examples.demo_activity import demo_activity
from src.core.context import WorkflowContext

from src.core.workflow import Workflow
from src.decorators.workflow import step, workflow


class DemoInput(TypedDict):
    message: str


class DemoState(TypedDict):
    count: int


@workflow(
    name="DemoWorkflow",
    description="A demo workflow for showcasing functionality.",
    version="0.1.0",
)
class DemoWorkflow(Workflow[DemoInput, DemoState]):
    @step(name="CustomStep1", description="A custom step in the workflow.")
    async def custom_step1(self, ctx: WorkflowContext[DemoInput, DemoState]):
        name = await ctx.activity(demo_activity)
        print(f"Hello, {name}!")

    @step()
    async def run(self, ctx: WorkflowContext[DemoInput, DemoState]):
        print("Running the demo workflow...")

    @step(name="CustomStep", description="A custom step in the workflow.")
    async def custom_step(self, ctx: WorkflowContext[DemoInput, DemoState]):
        print("Executing the custom step...")
