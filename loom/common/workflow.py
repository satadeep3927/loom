import importlib
import sys
from typing import Any, Type

from ..core.workflow import Workflow


def workflow_registry(module: str, cls: str) -> Type[Workflow[Any, Any]]:
    """
    Retrieve a workflow class from the global registry.

    Args:
        module: The module name where the workflow is defined.
        cls: The class name of the workflow.

    Returns:
        The workflow class with proper typing.

    Example:
        ```python
        # Get a workflow class dynamically
        WorkflowCls = workflow_registry("myapp.workflows", "UserOnboardingWorkflow")

        # Compile and use it
        compiled_workflow = WorkflowCls.compile()
        handle = await compiled_workflow.start(input_data)
        ```

    Raises:
        ModuleNotFoundError: If the module cannot be imported.
        AttributeError: If the class doesn't exist in the module.
        TypeError: If the retrieved class is not a Workflow subclass.
    """
    try:
        workflow_module = importlib.import_module(module)
        
        # Force reload the module to get latest changes
        if module in sys.modules:
            workflow_module = importlib.reload(workflow_module)
            
    except ModuleNotFoundError as e:
        raise ModuleNotFoundError(
            f"Cannot import workflow module '{module}'. "
            f"Ensure the module exists and is in the Python path."
        ) from e

    try:
        workflow_cls: Type[Workflow[Any, Any]] = getattr(workflow_module, cls)
    except AttributeError as e:
        raise AttributeError(
            f"Workflow class '{cls}' not found in module '{module}'. "
            f"Available classes: {[name for name in dir(workflow_module) if not name.startswith('_')]}"
        ) from e

    # Validate that it's actually a Workflow subclass
    if not (isinstance(workflow_cls, type) and issubclass(workflow_cls, Workflow)):
        raise TypeError(
            f"Class '{cls}' from module '{module}' is not a Workflow subclass. "
            f"Got {type(workflow_cls).__name__}."
        )

    return workflow_cls
