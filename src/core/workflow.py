import inspect
from typing import Generic, List, TypeVar

from ..schemas.workflow import InputT, StateT, Step
from .compiled import CompiledWorkflow

# For better type inference in classmethods
Self = TypeVar("Self", bound="Workflow")


class Workflow(Generic[InputT, StateT]):
    """
    Abstract base class for defining typed workflows.

    This class provides the foundation for creating deterministic, durable workflows
    with strong typing support. Workflows are parameterized by:
    - InputT: The immutable input type for the workflow
    - StateT: The mutable state type that evolves during execution

    Example:
        @dataclass
        class MyInput:
            user_id: str

        @dataclass
        class MyState:
            processed: bool = False
            result: str = ""

        @loom.workflow
        class MyWorkflow(Workflow[MyInput, MyState]):
            @loom.step
            async def process(self, ctx: WorkflowContext[MyState]):
                # Workflow logic here
                pass
    """

    @classmethod
    def compile(cls) -> CompiledWorkflow[InputT, StateT]:
        """
        Compile the workflow definition directly from the class.

        This is a convenience method that allows calling SomeWorkflow.compile()
        instead of SomeWorkflow().compile().

        Returns:
            CompiledWorkflow: A compiled, immutable workflow definition ready for execution

        Raises:
            ValueError: If the workflow has no steps defined or is malformed
        """
        # Create instance and delegate to instance method
        instance = cls()
        return instance._compile_instance()

    def _compile_instance(self) -> CompiledWorkflow[InputT, StateT]:
        """
        Internal instance compilation method.

        This method introspects the class to extract:
        - Workflow metadata (name, description, version)
        - Step definitions and their order
        - Validation of workflow structure

        Returns:
            CompiledWorkflow: A compiled, immutable workflow definition ready for execution

        Raises:
            ValueError: If the workflow has no steps defined or is malformed
        """
        # Extract workflow metadata with sensible defaults
        name = self._get_workflow_name()
        description = self._get_workflow_description()
        version = self._get_workflow_version()
        module = self._get_workflow_module()

        # Discover and validate workflow steps
        steps = self._discover_workflow_steps()

        # Validate workflow structure
        self._validate_workflow(steps)

        return CompiledWorkflow[InputT, StateT](
            name=name,
            description=description,
            version=version,
            module=module,
            steps=steps,
        )

    def _get_workflow_name(self) -> str:
        """Get the workflow name from metadata or class name."""
        return getattr(self, "_workflow_name", self.__class__.__name__)

    def _get_workflow_description(self) -> str:
        """Get the workflow description from metadata or docstring."""
        explicit_desc = getattr(self, "_workflow_description", "")
        if explicit_desc:
            return explicit_desc

        # Fallback to class docstring first line
        docstring = self.__class__.__doc__
        if docstring:
            return docstring.strip().split("\n")[0]

        return ""

    def _get_workflow_version(self) -> str:
        """Get the workflow version from metadata."""
        return getattr(self, "_workflow_version", "1.0.0")

    def _get_workflow_module(self) -> str:
        """Get the workflow module path."""
        return getattr(self, "_workflow_module", self.__class__.__module__)

    def _discover_workflow_steps(self) -> List[Step]:
        """
        Discover all workflow steps by introspecting decorated methods.

        Returns:
            List[Step]: Ordered list of step definitions
        """
        steps: List[Step] = []
        # Get all callable attributes that are decorated as steps
        for attr_name in self.__class__.__dict__:
            if attr_name.startswith("_"):
                continue

            attr = getattr(self, attr_name)
            if callable(attr) and hasattr(attr, "_step_name"):
                step_info: Step = {
                    "name": getattr(attr, "_step_name"),
                    "description": getattr(attr, "_step_description", ""),
                    "fn": attr.__name__,
                }
                steps.append(step_info)

        return steps

    def _validate_workflow(self, steps: List[Step]) -> None:
        """
        Validate the workflow structure and step signatures.
        Args:
            steps (List[Step]): The list of discovered
        Raises:
            ValueError: If the workflow is malformed
        """
        if not steps:
            raise ValueError(
                f"Workflow '{self.__class__.__name__}' must have at least one step"
            )
        seen = set()

        for step in steps:
            name = step["name"]
            if name in seen:
                raise ValueError(f"Duplicate step name: {name}")
            seen.add(name)

            fn = getattr(self, step["fn"])
            sig = inspect.signature(fn)
            params = list(sig.parameters.values())

            # bound method → first param is self
            if len(params) != 1:
                raise ValueError(
                    f"Step '{name}' must have signature (self, ctx), " f"got {sig}"
                )
