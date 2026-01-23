import trace
import traceback
from ..common.errors import StopReplay
from ..database.db import Database
from .engine import Engine


async def run_once():
    async with Database() as db:
        task = await db.claim_task()
        if not task:
            return
        workflow_id = task["workflow_id"]
        try:
            if task["kind"] == "STEP":
                await Engine.replay_until_block(workflow_id)
            elif task["kind"] == "ACTIVITY":
                await Engine.replay_activity(task)
            await db.task_completed(task["id"])
        except StopReplay:
            pass
        except Exception as e:
            traceback.print_exc()
            await db.task_failed(task["id"], str(e))
