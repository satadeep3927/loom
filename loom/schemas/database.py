from typing import TypedDict

from loom.schemas.workflow import Step


class Migration(TypedDict):
    name: str
    sql: str


class WorkflowInput(TypedDict):
    name: str
    description: str
    version: str
    status: str
    module: str
    steps: list[Step]
