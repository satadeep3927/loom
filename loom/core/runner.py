import datetime
import traceback

from ..common.errors import StopReplay
from ..database import Database
from .engine import Engine


async def run_once() -> bool:
    """Execute a single task from the queue.

    Returns:
        bool: True if a task was executed, False if no tasks available
    """
    db = Database()
    async with db:
        task = await db.claim_task()
        if not task:
            return False

        workflow_id = task["workflow_id"]
        is_completed = await db.workflow_is_completed(workflow_id)
        if is_completed:
            await db.task_completed(task["id"])
            return True

        try:
            if task["kind"] == "STEP":
                await Engine.replay_until_block(workflow_id)
            elif task["kind"] == "ACTIVITY":
                await Engine.replay_activity(task)
            elif task["kind"] == "TIMER":
                now = datetime.datetime.now(datetime.timezone.utc)
                run_at = datetime.datetime.fromisoformat(task["run_at"])
                if now < run_at:
                    await db.release_task(task["id"])
                    return True

                await db.create_event(
                    workflow_id=workflow_id,
                    type="TIMER_FIRED",
                    payload={},
                )

                await db.rotate_workflow_driver(task["workflow_id"])
            await db.task_completed(task["id"])
            return True
        except StopReplay:
            return True
        except Exception as e:
            traceback.print_exc()
            await db.task_failed(task["id"], str(e))

            # Mark workflow as failed when unhandled exception occurs
            await db.workflow_failed(
                workflow_id=workflow_id,
                error=str(e),
                task_id=task["id"],
                task_kind=task["kind"],
            )

            return True
