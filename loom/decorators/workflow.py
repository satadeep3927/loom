from ..schemas.workflow import ClsT, Func


def workflow(
    name: str | None = None,
    description: str | None = None,
    version: str = "1.0.0",
):
    """
    Decorator to define a workflow class.

    Args:
        name (str | None): The name of the workflow. Defaults to the class name if None.
        description (str | None): A brief description of the workflow. Defaults to an empty string if None.
        version (str): The version of the workflow. Defaults to "1.0.0".
    """

    def decorator(cls: ClsT) -> ClsT:
        setattr(cls, "_workflow_name", name or getattr(cls, "__name__"))
        setattr(cls, "_workflow_classname", getattr(cls, "__name__"))
        setattr(cls, "_workflow_module", getattr(cls, "__module__"))
        setattr(cls, "_workflow_description", description or "")
        setattr(cls, "_workflow_version", version)
        return cls

    return decorator


def step(
    name: str | None = None,
    description: str | None = None,
):
    """
    Decorator to define a step method within a workflow.

    Args:
        name (str | None): The name of the step. Defaults to the method name if None.
        description (str | None): A brief description of the step. Defaults to an empty string if None.
    """

    def decorator(func: Func) -> Func:
        setattr(func, "_step_name", name or getattr(func, "__name__"))
        setattr(func, "_step_description", description or "")
        return func

    return decorator
