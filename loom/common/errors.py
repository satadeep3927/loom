class WorkflowNotFoundError(Exception):
    """Exception raised when a workflow is not found in the database."""

    pass


class WorkflowStillRunningError(Exception):
    """Exception raised when attempting to retrieve the result of a running workflow."""

    pass


class WorkflowExecutionError(Exception):
    """Exception raised when a workflow has failed during execution."""

    pass


class ActivityFailedError(Exception):
    """Exception raised when an activity has permanently failed after all retries."""

    def __init__(self, activity_name: str, error_message: str):
        self.activity_name = activity_name
        self.error_message = error_message
        super().__init__(f"Activity '{activity_name}' failed: {error_message}")


class WorkerCancelledError(Exception):
    """Exception raised when a worker has been cancelled."""

    pass


class StopReplay(Exception):  # noqa: N818
    """
    Exception used to signal that workflow replay should stop.

    This is typically raised internally during workflow execution replay
    when the workflow reaches a point where it needs to wait for external input
    or events, indicating that replay cannot proceed further at this time.

    Example usage:

        from loom import loom
        from loom.schemas.workflow import Workflow, WorkflowContext, InputT, StateT

        class MyInput(InputT):
            pass

        class MyState(StateT):
            pass

        result: str = ""

        @loom.workflow
        class MyWorkflow(Workflow[MyInput, MyState]):
            @loom.step
            async def process(self, ctx: WorkflowContext[MyState]):
                # Workflow logic here
                pass
    """

    pass


class NonDeterministicWorkflowError(Exception):
    """Exception raised when a workflow execution diverges from its recorded history.

    This typically indicates that the workflow code has changed in a way that
    affects its execution path, leading to inconsistencies during replay.
    """

    pass
