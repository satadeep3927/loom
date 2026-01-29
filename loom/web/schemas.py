"""API Schema Definitions

This module contains Pydantic models that define the structure of API requests
and responses for the Loom web dashboard.
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

# === Enums ===


class WorkflowStatus(str, Enum):
    """Workflow execution status"""

    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELED = "CANCELED"


class TaskStatus(str, Enum):
    """Task execution status"""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class TaskKind(str, Enum):
    """Task type/kind"""

    STEP = "STEP"
    ACTIVITY = "ACTIVITY"
    TIMER = "TIMER"


class EventType(str, Enum):
    """Workflow event types"""

    WORKFLOW_STARTED = "WORKFLOW_STARTED"
    WORKFLOW_COMPLETED = "WORKFLOW_COMPLETED"
    WORKFLOW_FAILED = "WORKFLOW_FAILED"
    WORKFLOW_CANCELLED = "WORKFLOW_CANCELLED"
    STEP_START = "STEP_START"
    STEP_END = "STEP_END"
    STATE_SET = "STATE_SET"
    STATE_UPDATE = "STATE_UPDATE"
    ACTIVITY_SCHEDULED = "ACTIVITY_SCHEDULED"
    ACTIVITY_COMPLETED = "ACTIVITY_COMPLETED"
    ACTIVITY_FAILED = "ACTIVITY_FAILED"
    TIMER_SCHEDULED = "TIMER_SCHEDULED"
    TIMER_FIRED = "TIMER_FIRED"
    SIGNAL_RECEIVED = "SIGNAL_RECEIVED"


class LogLevel(str, Enum):
    """Log severity levels"""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


# === Base Response Models ===


class PaginationMeta(BaseModel):
    """Pagination metadata for list responses"""

    page: int = Field(..., description="Current page number (1-based)")
    per_page: int = Field(..., description="Items per page")
    total: int = Field(..., description="Total number of items")
    pages: int = Field(..., description="Total number of pages")
    has_prev: bool = Field(..., description="True if there is a previous page")
    has_next: bool = Field(..., description="True if there is a next page")


class PaginatedResponse[T](BaseModel):
    """Generic paginated response wrapper"""

    data: List[T] = Field(..., description="List of items for current page")
    meta: PaginationMeta = Field(..., description="Pagination metadata")


# === Workflow Models ===


class WorkflowSummary(BaseModel):
    """Workflow summary for list views"""

    id: str = Field(
        ...,
        description="Unique workflow identifier",
        examples=["wf_01HQK8X9M2Y3Z4A5B6C7D8E9F0"],
    )
    name: str = Field(
        ...,
        description="Workflow name/type",
        examples=[
            "UserRegistrationWorkflow",
            "OrderProcessingWorkflow",
            "DataPipelineWorkflow",
        ],
    )
    status: WorkflowStatus = Field(..., description="Current execution status")
    created_at: datetime = Field(
        ..., description="When workflow was created (ISO 8601 format)"
    )
    updated_at: datetime = Field(
        ..., description="When workflow was last updated (ISO 8601 format)"
    )
    duration: Optional[int] = Field(
        None,
        description="Execution duration in seconds (if completed)",
        examples=[120, 1800, 45],
    )

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}
        json_schema_extra = {
            "examples": [
                {
                    "id": "wf_01HQK8X9M2Y3Z4A5B6C7D8E9F0",
                    "name": "UserRegistrationWorkflow",
                    "status": "COMPLETED",
                    "created_at": "2026-01-29T10:15:00Z",
                    "updated_at": "2026-01-29T10:17:30Z",
                    "duration": 150,
                },
                {
                    "id": "wf_01HQK8X9M2Y3Z4A5B6C7D8E9F1",
                    "name": "OrderProcessingWorkflow",
                    "status": "RUNNING",
                    "created_at": "2026-01-29T10:20:00Z",
                    "updated_at": "2026-01-29T10:25:15Z",
                    "duration": None,
                },
            ]
        }


class WorkflowDetail(BaseModel):
    """Complete workflow information"""

    id: str = Field(
        ...,
        description="Unique workflow identifier",
        examples=["wf_01HQK8X9M2Y3Z4A5B6C7D8E9F0"],
    )
    name: str = Field(
        ..., description="Workflow name/type", examples=["UserRegistrationWorkflow"]
    )
    description: Optional[str] = Field(
        None,
        description="Workflow description",
        examples=[
            "Handles new user registration with email verification and profile setup"
        ],
    )
    version: str = Field(
        ..., description="Workflow version", examples=["1.0.0", "2.1.3", "1.0.0-beta.1"]
    )
    module: str = Field(
        ...,
        description="Python module containing workflow",
        examples=["workflows.user_registration", "workflows.order_processing"],
    )
    status: WorkflowStatus = Field(..., description="Current execution status")
    input: Dict[str, Any] = Field(
        ...,
        description="Workflow input data (JSON)",
        examples=[
            {"user_id": 12345, "email": "user@example.com", "plan": "premium"},
            {"order_id": "ord_123", "items": [{"id": "item_1", "quantity": 2}]},
        ],
    )
    created_at: datetime = Field(
        ..., description="When workflow was created (ISO 8601 format)"
    )
    updated_at: datetime = Field(
        ..., description="When workflow was last updated (ISO 8601 format)"
    )

    # Computed fields
    duration: Optional[int] = Field(
        None, description="Execution duration in seconds", examples=[150, 3600, None]
    )
    event_count: int = Field(
        ..., description="Total number of events", examples=[12, 45, 3]
    )
    current_state: Dict[str, Any] = Field(
        default_factory=dict,
        description="Current workflow state reconstructed from events",
        examples=[
            {"step": "email_verification", "verified": True, "profile_created": False},
            {"order_status": "payment_pending", "inventory_reserved": True},
        ],
    )

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}
        json_schema_extra = {
            "examples": [
                {
                    "id": "wf_01HQK8X9M2Y3Z4A5B6C7D8E9F0",
                    "name": "UserRegistrationWorkflow",
                    "description": "Handles new user registration with email verification",
                    "version": "1.0.0",
                    "module": "workflows.user_registration",
                    "status": "COMPLETED",
                    "input": {
                        "user_id": 12345,
                        "email": "user@example.com",
                        "plan": "premium",
                    },
                    "created_at": "2026-01-29T10:15:00Z",
                    "updated_at": "2026-01-29T10:17:30Z",
                    "duration": 150,
                    "event_count": 12,
                    "current_state": {
                        "email_verified": True,
                        "profile_created": True,
                        "welcome_email_sent": True,
                    },
                }
            ]
        }


# === Task Models ===


class TaskSummary(BaseModel):
    """Task summary for list views"""

    id: str = Field(
        ...,
        description="Unique task identifier",
        examples=["task_01HQK8XA1B2C3D4E5F6G7H8I9J"],
    )
    workflow_id: str = Field(
        ...,
        description="Parent workflow ID",
        examples=["wf_01HQK8X9M2Y3Z4A5B6C7D8E9F0"],
    )
    workflow_name: str = Field(
        ..., description="Parent workflow name", examples=["UserRegistrationWorkflow"]
    )
    kind: TaskKind = Field(..., description="Task type/kind")
    target: str = Field(
        ...,
        description="Task target (step name, activity name, etc.)",
        examples=[
            "send_welcome_email",
            "UserRegistration.verify_email",
            "payment_timeout",
        ],
    )
    status: TaskStatus = Field(..., description="Current task status")
    attempts: int = Field(
        ..., description="Number of execution attempts", examples=[1, 2, 3]
    )
    max_attempts: int = Field(
        ..., description="Maximum allowed attempts", examples=[3, 5, 10]
    )
    run_at: datetime = Field(
        ..., description="When task should/did run (ISO 8601 format)"
    )
    created_at: datetime = Field(
        ..., description="When task was created (ISO 8601 format)"
    )
    updated_at: Optional[datetime] = Field(
        None, description="When task was last updated (ISO 8601 format)"
    )
    last_error: Optional[str] = Field(
        None,
        description="Last error message (if failed)",
        examples=[
            "SMTP connection failed: Unable to connect to mail server",
            "HTTP 429: Rate limit exceeded",
            "Database connection timeout after 30s",
        ],
    )

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}
        json_schema_extra = {
            "examples": [
                {
                    "id": "task_01HQK8XA1B2C3D4E5F6G7H8I9J",
                    "workflow_id": "wf_01HQK8X9M2Y3Z4A5B6C7D8E9F0",
                    "workflow_name": "UserRegistrationWorkflow",
                    "kind": "ACTIVITY",
                    "target": "send_welcome_email",
                    "status": "COMPLETED",
                    "attempts": 1,
                    "max_attempts": 3,
                    "run_at": "2026-01-29T10:16:00Z",
                    "created_at": "2026-01-29T10:15:30Z",
                    "updated_at": "2026-01-29T10:16:15Z",
                    "last_error": None,
                },
                {
                    "id": "task_01HQK8XA1B2C3D4E5F6G7H8I9K",
                    "workflow_id": "wf_01HQK8X9M2Y3Z4A5B6C7D8E9F1",
                    "workflow_name": "OrderProcessingWorkflow",
                    "kind": "ACTIVITY",
                    "target": "charge_payment",
                    "status": "FAILED",
                    "attempts": 3,
                    "max_attempts": 3,
                    "run_at": "2026-01-29T10:21:30Z",
                    "created_at": "2026-01-29T10:21:00Z",
                    "updated_at": "2026-01-29T10:23:45Z",
                    "last_error": "Payment failed: Insufficient funds",
                },
            ]
        }


class TaskDetail(TaskSummary):
    """Complete task information (extends TaskSummary)"""

    ...


# === Event Models ===


class EventSummary(BaseModel):
    """Event summary for list views"""

    id: int = Field(..., description="Unique event identifier (sequence number)")
    workflow_id: str = Field(..., description="Parent workflow ID")
    type: EventType = Field(..., description="Event type")
    payload: Dict[str, Any] = Field(..., description="Event data (JSON)")
    created_at: datetime = Field(..., description="When event was created")

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class EventDetail(EventSummary):
    """Complete event information (extends EventSummary)"""

    workflow_name: str = Field(..., description="Parent workflow name")
    workflow_status: WorkflowStatus = Field(
        ..., description="Workflow status when event occurred"
    )


# === Log Models ===


class LogEntry(BaseModel):
    """Workflow log entry"""

    id: int = Field(..., description="Unique log entry identifier")
    workflow_id: str = Field(..., description="Parent workflow ID")
    workflow_name: str = Field(..., description="Parent workflow name")
    level: LogLevel = Field(..., description="Log severity level")
    message: str = Field(..., description="Log message content")
    created_at: datetime = Field(..., description="When log entry was created")

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


# === Statistics Models ===


class WorkflowStats(BaseModel):
    """Workflow execution statistics"""

    total: int = Field(..., description="Total number of workflows")
    running: int = Field(..., description="Number of running workflows")
    completed: int = Field(..., description="Number of completed workflows")
    failed: int = Field(..., description="Number of failed workflows")
    canceled: int = Field(..., description="Number of canceled workflows")


class TaskStats(BaseModel):
    """Task execution statistics"""

    total: int = Field(..., description="Total number of tasks")
    pending: int = Field(..., description="Number of pending tasks")
    running: int = Field(..., description="Number of running tasks")
    completed: int = Field(..., description="Number of completed tasks")
    failed: int = Field(..., description="Number of failed tasks")


class SystemStats(BaseModel):
    """Overall system statistics"""

    workflows: WorkflowStats = Field(..., description="Workflow statistics")
    tasks: TaskStats = Field(..., description="Task statistics")
    events: int = Field(..., description="Total number of events")
    logs: int = Field(..., description="Total number of log entries")


# === Request Models ===

# === Request Parameter Models ===


class WorkflowListParams(BaseModel):
    """Parameters for workflow list endpoint"""

    page: int = Field(1, ge=1, description="Page number (1-based)", examples=[1, 2, 10])
    per_page: int = Field(
        50,
        ge=1,
        le=1000,
        description="Items per page (max 1000)",
        examples=[10, 50, 100],
    )
    status: Optional[WorkflowStatus] = Field(
        None, description="Filter by workflow execution status"
    )
    name: Optional[str] = Field(
        None,
        description="Filter by workflow name (partial match, case-insensitive)",
        examples=["User", "Registration", "Order"],
    )
    sort_by: str = Field(
        "created_at",
        description="Field to sort by",
        examples=["created_at", "updated_at", "name", "status"],
    )
    sort_order: str = Field(
        "desc",
        pattern="^(asc|desc)$",
        description="Sort order (asc=ascending, desc=descending)",
        examples=["asc", "desc"],
    )

    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "page": 1,
                    "per_page": 50,
                    "status": "RUNNING",
                    "name": "User",
                    "sort_by": "created_at",
                    "sort_order": "desc",
                }
            ]
        }


class TaskListParams(BaseModel):
    """Parameters for task list endpoint"""

    page: int = Field(1, ge=1, description="Page number (1-based)", examples=[1, 2, 5])
    per_page: int = Field(
        50,
        ge=1,
        le=1000,
        description="Items per page (max 1000)",
        examples=[25, 50, 100],
    )
    workflow_id: Optional[str] = Field(
        None,
        description="Filter by specific workflow ID",
        examples=["wf_01HQK8X9M2Y3Z4A5B6C7D8E9F0"],
    )
    status: Optional[TaskStatus] = Field(
        None, description="Filter by task execution status"
    )
    kind: Optional[TaskKind] = Field(None, description="Filter by task type/kind")
    sort_by: str = Field(
        "created_at",
        description="Field to sort by",
        examples=["created_at", "run_at", "status", "attempts"],
    )
    sort_order: str = Field(
        "desc",
        pattern="^(asc|desc)$",
        description="Sort order (asc=ascending, desc=descending)",
        examples=["asc", "desc"],
    )

    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "page": 1,
                    "per_page": 50,
                    "workflow_id": "wf_01HQK8X9M2Y3Z4A5B6C7D8E9F0",
                    "status": "PENDING",
                    "kind": "ACTIVITY",
                    "sort_by": "run_at",
                    "sort_order": "asc",
                }
            ]
        }


class EventListParams(BaseModel):
    """Parameters for event list endpoint"""

    page: int = Field(1, ge=1, description="Page number (1-based)", examples=[1, 3, 15])
    per_page: int = Field(
        100,
        ge=1,
        le=1000,
        description="Items per page (max 1000)",
        examples=[50, 100, 200],
    )
    workflow_id: Optional[str] = Field(
        None,
        description="Filter by specific workflow ID",
        examples=["wf_01HQK8X9M2Y3Z4A5B6C7D8E9F0"],
    )
    type: Optional[EventType] = Field(None, description="Filter by event type")
    since: Optional[datetime] = Field(
        None, description="Filter events created after this timestamp (ISO 8601 format)"
    )
    sort_by: str = Field(
        "id", description="Field to sort by", examples=["id", "created_at", "type"]
    )
    sort_order: str = Field(
        "desc",
        pattern="^(asc|desc)$",
        description="Sort order (asc=ascending, desc=descending)",
        examples=["asc", "desc"],
    )

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}
        json_schema_extra = {
            "examples": [
                {
                    "page": 1,
                    "per_page": 100,
                    "workflow_id": "wf_01HQK8X9M2Y3Z4A5B6C7D8E9F0",
                    "type": "ACTIVITY_COMPLETED",
                    "since": "2026-01-29T10:00:00Z",
                    "sort_by": "created_at",
                    "sort_order": "desc",
                }
            ]
        }


class LogListParams(BaseModel):
    """Parameters for log list endpoint"""

    page: int = Field(1, ge=1, description="Page number (1-based)", examples=[1, 2, 8])
    per_page: int = Field(
        100,
        ge=1,
        le=1000,
        description="Items per page (max 1000)",
        examples=[50, 100, 250],
    )
    workflow_id: Optional[str] = Field(
        None,
        description="Filter by specific workflow ID",
        examples=["wf_01HQK8X9M2Y3Z4A5B6C7D8E9F0"],
    )
    level: Optional[LogLevel] = Field(None, description="Filter by minimum log level")
    since: Optional[datetime] = Field(
        None, description="Filter logs created after this timestamp (ISO 8601 format)"
    )
    sort_by: str = Field(
        "created_at",
        description="Field to sort by",
        examples=["created_at", "level", "workflow_id"],
    )
    sort_order: str = Field(
        "desc",
        pattern="^(asc|desc)$",
        description="Sort order (asc=ascending, desc=descending)",
        examples=["asc", "desc"],
    )

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}
        json_schema_extra = {
            "examples": [
                {
                    "page": 1,
                    "per_page": 100,
                    "workflow_id": "wf_01HQK8X9M2Y3Z4A5B6C7D8E9F0",
                    "level": "ERROR",
                    "since": "2026-01-29T09:00:00Z",
                    "sort_by": "created_at",
                    "sort_order": "desc",
                }
            ]
        }


# === Error Models ===


class ErrorResponse(BaseModel):
    """Standard error response"""

    error: str = Field(
        ...,
        description="Error type/code",
        examples=["VALIDATION_ERROR", "NOT_FOUND", "INTERNAL_ERROR", "BAD_REQUEST"],
    )
    message: str = Field(
        ...,
        description="Human-readable error message",
        examples=[
            "Workflow not found",
            "Invalid page parameter: must be >= 1",
            "Database connection failed",
            "Invalid sort field: 'invalid_field'",
        ],
    )
    details: Optional[Dict[str, Any]] = Field(
        None,
        description="Additional error details and context",
        examples=[
            {
                "workflow_id": "wf_123",
                "available_fields": ["created_at", "updated_at", "name"],
            },
            {"field": "per_page", "max_value": 1000, "provided": 1500},
        ],
    )

    class Config:
        json_schema_extra = {
            "examples": [
                {
                    "error": "NOT_FOUND",
                    "message": "Workflow 'wf_01HQK8X9M2Y3Z4A5B6C7D8E9F0' not found",
                    "details": {
                        "workflow_id": "wf_01HQK8X9M2Y3Z4A5B6C7D8E9F0",
                        "resource": "workflow",
                    },
                },
                {
                    "error": "VALIDATION_ERROR",
                    "message": "Invalid pagination parameters",
                    "details": {
                        "field": "per_page",
                        "max_value": 1000,
                        "provided": 1500,
                    },
                },
            ]
        }
