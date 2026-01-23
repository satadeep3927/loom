from typing import Any, List, TypedDict, TypeVar

FuncReturn = TypeVar("FuncReturn")


class ActivityMetadata(TypedDict):
    name: str
    description: str
    retry_count: int
    args: List[Any]
    timeout_seconds: int
    func: str
    module: str
