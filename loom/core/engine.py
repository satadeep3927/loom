import json
from datetime import datetime, timedelta, timezone
from typing import Generic

from ..common.activity import load_activity
from ..common.errors import ActivityFailedError, StopReplay
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
                if task["attempts"] >= task["max_attempts"]:
                    await db.task_failed(task["id"], str(e))
                    await db.create_event(
                        workflow_id=task["workflow_id"],
                        type="ACTIVITY_FAILED",
                        payload={
                            "name": task["target"],
                            "error": str(e),
                        },
                    )
                else:

                    delay = min(60, 2 ** task["attempts"])
                    next_run = datetime.now(timezone.utc) + timedelta(seconds=delay)
                    await db.schedule_retry(task["id"], next_run, str(e))

    @staticmethod
    async def replay_until_block(workflow_id: str) -> None:
        # Load workflow event history
        async with Database[InputT, StateT]() as db:
            workflow_def = await db.get_workflow_info(workflow_id)
            history = await db.get_workflow_events(workflow_id=workflow_def["id"])
        workflow_input = json.loads(workflow_def["input"])

        ctx: WorkflowContext = WorkflowContext(
            workflow_def["id"], workflow_input, history, {}
        )

        first_event = ctx._peek()
        if first_event and first_event["type"] == "WORKFLOW_STARTED":
            ctx._consume()

        workflow_cls = workflow_registry(workflow_def["module"], workflow_def["name"])
        workflow = workflow_cls()
        steps = workflow._discover_workflow_steps()

        try:
            for step in steps:
                # Check for and consume STEP_START event during replay
                step_start_event = ctx._match_event("STEP_START")
                if step_start_event:
                    if step_start_event["payload"]["step_name"] != step["name"]:
                        raise StopReplay  # Step mismatch, something changed
                    ctx._consume()
                else:
                    # Not replaying, emit STEP_START event
                    if not ctx.is_replaying:
                        await ctx._append_event(
                            "STEP_START",
                            {
                                "step_name": step["name"],
                                "step_fn": step["fn"],
                                "started_at": datetime.now(timezone.utc).isoformat(),
                            },
                        )

                step_fn = getattr(workflow, step["fn"])
                await step_fn(ctx)

                # Check for and consume STEP_END event during replay
                step_end_event = ctx._match_event("STEP_END")
                if step_end_event:
                    ctx._consume()
                else:
                    # Not replaying, emit STEP_END event
                    if not ctx.is_replaying:
                        await ctx._append_event(
                            "STEP_END",
                            {
                                "step_name": step["name"],
                                "completed_at": datetime.now(timezone.utc).isoformat(),
                            },
                        )

        except StopReplay:
            last = ctx.last_emitted_event_type()
            if last in ("STATE_SET", "STATE_UPDATE"):
                async with Database[InputT, StateT]() as db:
                    await db.rotate_workflow_driver(workflow_id)
            return
        except ActivityFailedError as e:
            # Activity failed permanently, mark workflow as failed
            async with Database[InputT, StateT]() as db:
                await db.workflow_failed(
                    workflow_id,
                    error=f"Activity '{e.activity_name}' failed: {e.error_message}",
                )
            return
        except Exception as e:
            # Unexpected error during workflow execution
            async with Database[InputT, StateT]() as db:
                await db.workflow_failed(workflow_id, error=str(e))
            return

        async with Database[InputT, StateT]() as db:
            await db.complete_workflow(workflow_id)
