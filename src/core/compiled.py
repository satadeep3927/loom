from typing import Generic, List

from ..core.handle import WorkflowHandle
from ..database.db import Database
from ..schemas.database import WorkflowInput
from ..schemas.workflow import InputT, StateT, Step


class CompiledWorkflow(Generic[InputT, StateT]):
    name: str
    description: str
    version: str
    module: str
    steps: List[Step]

    def __init__(
        self,
        name: str,
        description: str,
        version: str,
        module: str,
        steps: List[Step],
    ):
        self.name = name
        self.description = description
        self.version = version
        self.module = module
        self.steps = steps

    async def start(self, input: InputT):
        workflow: WorkflowInput = {
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "status": "RUNNING",
            "module": self.module,
            "steps": self.steps,
        }
        async with Database[InputT, StateT]() as db:
            workflow_id = await db.create_workflow(workflow, input)
        return WorkflowHandle[InputT, StateT](workflow_id)
