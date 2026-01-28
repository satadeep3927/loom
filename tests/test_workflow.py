"""Tests for workflow definition and compilation."""

import pytest

from src.core.context import WorkflowContext
from src.core.workflow import Workflow
from src.decorators.workflow import step, workflow


class TestInput(dict):
    message: str


class TestState(dict):
    count: int


@workflow(name="TestWorkflow", version="1.0.0", description="Test workflow")
class TestWorkflow(Workflow[TestInput, TestState]):
    @step(name="step1")
    async def first_step(self, ctx: WorkflowContext[TestInput, TestState]):
        await ctx.state.set("count", 1)

    @step(name="step2")
    async def second_step(self, ctx: WorkflowContext[TestInput, TestState]):
        count = ctx.state.get("count", 0)
        await ctx.state.set("count", count + 1)


def test_workflow_decorator():
    """Test that @workflow decorator sets metadata correctly."""
    assert hasattr(TestWorkflow, "_workflow_name")
    assert TestWorkflow._workflow_name == "TestWorkflow"  # type: ignore
    assert TestWorkflow._workflow_version == "1.0.0"  # type: ignore
    assert TestWorkflow._workflow_description == "Test workflow"  # type: ignore


def test_step_decorator():
    """Test that @step decorator sets metadata correctly."""
    wf = TestWorkflow()
    assert hasattr(wf.first_step, "_step_name")
    assert wf.first_step._step_name == "step1"  # type: ignore


def test_workflow_compilation():
    """Test workflow compilation."""
    compiled = TestWorkflow.compile()

    assert compiled.name == "TestWorkflow"
    assert compiled.version == "1.0.0"
    assert compiled.description == "Test workflow"
    assert len(compiled.steps) == 2
    assert compiled.steps[0]["name"] == "step1"
    assert compiled.steps[1]["name"] == "step2"


def test_workflow_step_discovery():
    """Test that workflow discovers steps correctly."""
    wf = TestWorkflow()
    steps = wf._discover_workflow_steps()

    assert len(steps) == 2
    assert steps[0]["fn"] == "first_step"
    assert steps[1]["fn"] == "second_step"


def test_workflow_validation():
    """Test workflow validation."""

    @workflow(name="EmptyWorkflow")
    class EmptyWorkflow(Workflow[TestInput, TestState]):
        pass

    wf = EmptyWorkflow()
    with pytest.raises(ValueError, match="must have at least one step"):
        wf._compile_instance()


def test_workflow_name_defaults_to_classname():
    """Test that workflow name defaults to class name if not specified."""

    @workflow()
    class MyCustomWorkflow(Workflow[TestInput, TestState]):
        @step()
        async def some_step(self, ctx):
            pass

    assert MyCustomWorkflow._workflow_name == "MyCustomWorkflow"  # type: ignore
