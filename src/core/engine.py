from typing import Generic

from ..common.activity import load_activity
from ..common.workflow import workflow_registry
from ..database.db import Database
from ..schemas.activity import ActivityMetadata
from ..schemas.tasks import Task
from ..schemas.workflow import InputT, StateT
from .context import WorkflowContext


class Engine(Generic[InputT, StateT]):
    """Core workflow execution engine with replay capabilities.

    The Engine is responsible for workflow replay and step execution. It
    reconstructs workflow state from event history and executes steps in
    a deterministic manner, stopping when side effects are encountered.
    """

    @staticmethod
    async def replay_activity(task: Task):
        try:
            workflow_id = task["workflow_id"]
            activity_name = task["target"]
            async with Database[InputT, StateT]() as db:
                event = await db.get_activity_event(
                    workflow_id, activity_name, task["attempts"]
                )

            if not event:
                raise ValueError(
                    f"No event found for activity {activity_name} in workflow {workflow_id} on attempt {task['attempts']}"
                )

            metadata = ActivityMetadata(**event["payload"])  # type: ignore
            fn = load_activity(metadata["module"], metadata["func"])
            args = metadata["args"]
            response = await fn(*args)

            async with Database[InputT, StateT]() as db:
                await db.create_event(
                    workflow_id,
                    "ACTIVITY_COMPLETED",
                    payload={
                        "name": activity_name,
                        "result": response,
                    },
                )

                await db.task_completed(task["id"])
                await db.recreate_workflow_task(workflow_id)

        except Exception as e:
            async with Database[InputT, StateT]() as db:
                await db.task_failed(task["id"], str(e))

                if task["attempts"] + 1 >= task["max_attempts"]:
                    await db.create_event(
                        workflow_id=task["workflow_id"],
                        type="ACTIVITY_FAILED",
                        payload={
                            "name": task["target"],
                            "error": str(e),
                        },
                    )

    @staticmethod
    async def replay_until_block(workflow_id: str) -> None:
        """Replay workflow execution until a blocking operation is encountered.

        This method reconstructs workflow context from event history and
        re-executes workflow steps deterministically. Execution continues
        until a StopReplay exception is raised (typically when an activity
        needs to be scheduled or completed).

        Args:
            workflow_id: Unique identifier of the workflow instance to replay

        Note:
            This method is designed to be idempotent and safe to call
            multiple times for the same workflow instance.
        """
        # Load workflow event history
        async with Database[InputT, StateT]() as db:
            workflow_def = await db.get_workflow_info(workflow_id)
            history = await db.get_workflow_events(workflow_id=workflow_def["id"])

        # Create execution context
        ctx: WorkflowContext = WorkflowContext(
            workflow_def["id"], workflow_def["input"], history, {}
        )

        # Load workflow class and create instance
        workflow_cls = workflow_registry(workflow_def["module"], workflow_def["name"])
        workflow = workflow_cls()
        steps = workflow._discover_workflow_steps()

        for step in steps:
            step_fn = getattr(workflow, step["fn"])
            await step_fn(ctx)
