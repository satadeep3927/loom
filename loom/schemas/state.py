from typing import TypedDict


class State(TypedDict):
    """Represents the mutable state of a workflow.

    This schema defines the structure of the state object that is passed
    to each step of a workflow during its execution. The state is mutable
    and can be updated by workflow steps to reflect the current progress
    and data of the workflow.

    """

    ...


class Input(TypedDict):
    """Represents the immutable input to a workflow.

    This schema defines the structure of the input object that is provided
    when starting a new workflow instance. The input is immutable and
    remains constant throughout the lifecycle of the workflow.

    """

    ...
