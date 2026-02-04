from typing import Any, Dict, List

from pydantic import BaseModel, Field


class GraphNode(BaseModel):
    """Represents a node in the workflow definition graph."""

    id: str = Field(
        ...,
        description="Unique identifier for the node",
        examples=["step_process_payment", "activity_send_email", "state_user_id"],
    )
    type: str = Field(
        ...,
        description="Type of the node",
        examples=["step", "activity", "timer", "state"],
    )
    label: str = Field(
        ...,
        description="Display label for the node",
        examples=["Process Payment", "send_email", "Sleep 5s", "state.user_id"],
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata about the node",
        examples=[
            {
                "description": "Processes user payment",
                "function": "process_payment_step",
            },
            {"retry_count": 3, "timeout_seconds": 30},
            {"key": "user_id", "type": "string"},
        ],
    )


class GraphEdge(BaseModel):
    """Represents an edge (connection) in the workflow definition graph."""

    from_node: str = Field(
        ...,
        alias="from",
        description="Source node ID",
        examples=["step_validate_input", "state_user_data"],
    )
    to_node: str = Field(
        ...,
        alias="to",
        description="Target node ID",
        examples=["step_process_payment", "activity_send_notification"],
    )
    type: str = Field(
        ...,
        description="Type of relationship",
        examples=["sequence", "calls", "reads", "writes", "waits"],
    )
    label: str = Field(
        default="",
        description="Display label for the edge",
        examples=["then", "executes", "reads", "updates", "pauses for"],
    )


class WorkflowDefinitionGraph(BaseModel):
    """Complete workflow definition graph structure."""

    nodes: List[GraphNode] = Field(..., description="List of nodes in the graph")
    edges: List[GraphEdge] = Field(
        ..., description="List of edges connecting the nodes"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Workflow-level metadata",
        examples=[
            {
                "workflow_name": "OrderProcessingWorkflow",
                "workflow_version": "1.2.0",
                "workflow_description": "Processes customer orders with payment and shipping",
            }
        ],
    )

    class Config:
        json_encoders = {
            # Add any custom encoders if needed
        }
        json_schema_extra = {
            "examples": [
                {
                    "nodes": [
                        {
                            "id": "step_validate_order",
                            "type": "step",
                            "label": "Validate Order",
                            "metadata": {
                                "description": "Validates order data and inventory",
                                "function": "validate_order_step",
                            },
                        },
                        {
                            "id": "activity_check_inventory",
                            "type": "activity",
                            "label": "check_inventory",
                            "metadata": {
                                "called_from_step": "validate_order",
                                "retry_count": 3,
                            },
                        },
                        {
                            "id": "state_order_valid",
                            "type": "state",
                            "label": "state.order_valid",
                            "metadata": {"key": "order_valid"},
                        },
                    ],
                    "edges": [
                        {
                            "from": "step_validate_order",
                            "to": "activity_check_inventory",
                            "type": "calls",
                            "label": "executes",
                        },
                        {
                            "from": "step_validate_order",
                            "to": "state_order_valid",
                            "type": "writes",
                            "label": "updates",
                        },
                    ],
                    "metadata": {
                        "workflow_name": "OrderProcessingWorkflow",
                        "workflow_version": "1.0.0",
                        "workflow_description": "Handles order processing with validation and payment",
                    },
                }
            ]
        }


class GraphFormat(BaseModel):
    """Supported graph output formats."""

    format: str = Field(
        ...,
        description="Output format for the graph",
        examples=["mermaid", "dot", "json"],
    )


class GraphResponse(BaseModel):
    """Response containing the generated graph."""

    format: str = Field(
        ...,
        description="Format of the generated graph",
        examples=["mermaid", "dot", "json"],
    )
    content: str = Field(
        ..., description="Generated graph content in the specified format"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata about the graph generation",
    )
