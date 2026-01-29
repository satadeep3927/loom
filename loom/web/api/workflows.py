"""Workflow API Endpoints

Provides REST endpoints for managing and querying workflows.
"""

import json
import math
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from ...database.db import Database
from ..schemas import (
    ErrorResponse,
    EventListParams,
    EventSummary,
    LogEntry,
    LogListParams,
    PaginatedResponse,
    PaginationMeta,
    WorkflowDetail,
    WorkflowListParams,
    WorkflowStatus,
    WorkflowSummary,
)

router = APIRouter()


async def get_db():
    """Database dependency"""
    async with Database[Any, Any]() as db:
        yield db


def calculate_duration(workflow: dict) -> Optional[int]:
    """Calculate workflow duration in seconds if completed"""
    if workflow["status"] in ["COMPLETED", "FAILED", "CANCELED"]:
        from datetime import datetime

        created = datetime.fromisoformat(workflow["created_at"].replace("Z", "+00:00"))
        updated = datetime.fromisoformat(workflow["updated_at"].replace("Z", "+00:00"))
        return int((updated - created).total_seconds())
    return None


@router.get(
    "/",
    response_model=PaginatedResponse[WorkflowSummary],
    summary="List workflows",
    description="""
    Retrieve a paginated list of workflows with optional filtering and sorting.

    **Filtering Options:**
    - `status`: Filter by workflow execution status
    - `name`: Filter by workflow name (partial match, case-insensitive)

    **Sorting Options:**
    - `sort_by`: Field to sort by (created_at, updated_at, name, status)
    - `sort_order`: Sort direction (asc/desc)

    **Pagination:**
    - `page`: Page number (1-based)
    - `per_page`: Items per page (1-1000, default 50)

    **Response includes:**
    - List of workflow summaries for the requested page
    - Pagination metadata (total count, page info, etc.)
    """,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid request parameters"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
async def list_workflows(
    params: WorkflowListParams = Depends(), db: Database = Depends(get_db)
):
    """List workflows with pagination and filtering"""
    try:
        # Build WHERE clause
        where_conditions = []
        query_params = []

        if params.status:
            where_conditions.append("status = ?")
            query_params.append(params.status.value)

        if params.name:
            where_conditions.append("name LIKE ?")
            query_params.append(f"%{params.name}%")

        where_clause = (
            f"WHERE {' AND '.join(where_conditions)}" if where_conditions else ""
        )

        # Get total count
        count_sql = f"SELECT COUNT(*) as total FROM workflows {where_clause}"
        count_result = await db.fetchone(count_sql, tuple(query_params))
        total = count_result["total"] if count_result else 0

        # Calculate pagination
        pages = math.ceil(total / params.per_page) if total > 0 else 1
        offset = (params.page - 1) * params.per_page

        # Build ORDER BY clause
        order_clause = f"ORDER BY {params.sort_by} {params.sort_order.upper()}"

        # Get workflows for current page
        workflows_sql = f"""
            SELECT id, name, status, created_at, updated_at
            FROM workflows
            {where_clause}
            {order_clause}
            LIMIT {params.per_page} OFFSET {offset}
        """

        workflows = await db.query(workflows_sql, tuple(query_params))

        # Convert to response models
        workflow_summaries = [
            WorkflowSummary(
                id=w["id"],
                name=w["name"],
                status=WorkflowStatus(w["status"]),
                created_at=w["created_at"],
                updated_at=w["updated_at"],
                duration=calculate_duration(dict(w)),
            )
            for w in workflows
        ]

        # Build pagination metadata
        meta = PaginationMeta(
            page=params.page,
            per_page=params.per_page,
            total=total,
            pages=pages,
            has_prev=params.page > 1,
            has_next=params.page < pages,
        )

        return PaginatedResponse(data=workflow_summaries, meta=meta)

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to list workflows: {str(e)}"
        )


@router.get(
    "/{workflow_id}",
    response_model=WorkflowDetail,
    summary="Get workflow details",
    description="""
    Retrieve complete information for a specific workflow.

    **Returns:**
    - Complete workflow metadata (name, version, module, etc.)
    - Current execution status and timing information
    - Workflow input data and current state
    - Event count and computed statistics

    **Computed Fields:**
    - `duration`: Execution time in seconds (for completed workflows)
    - `event_count`: Total number of events generated
    - `current_state`: Reconstructed workflow state from events
    """,
    responses={
        404: {"model": ErrorResponse, "description": "Workflow not found"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
async def get_workflow(workflow_id: str, db: Database = Depends(get_db)):
    """Get detailed workflow information"""
    try:
        # Get workflow info
        workflow = await db.get_workflow_info(workflow_id)

        # Get event count
        event_count_sql = "SELECT COUNT(*) as count FROM events WHERE workflow_id = ?"
        event_count_result = await db.fetchone(event_count_sql, (workflow_id,))
        event_count = event_count_result["count"] if event_count_result else 0

        # Reconstruct current state from STATE_SET/STATE_UPDATE events
        state_events_sql = """
            SELECT type, payload FROM events
            WHERE workflow_id = ? AND type IN ('STATE_SET', 'STATE_UPDATE')
            ORDER BY id ASC
        """
        state_events = await db.query(state_events_sql, (workflow_id,))

        current_state = {}
        for event in state_events:
            payload = json.loads(event["payload"])
            if event["type"] == "STATE_SET":
                current_state[payload["key"]] = payload["value"]
            elif event["type"] == "STATE_UPDATE":
                current_state.update(payload["values"])

        return WorkflowDetail(
            id=workflow["id"],
            name=workflow["name"],
            description=workflow.get("description", ""),
            version=workflow["version"] if workflow.get("version") else "1.0.0",
            module=workflow["module"],
            status=WorkflowStatus(workflow["status"]),
            input=json.loads(workflow["input"]),
            created_at=workflow["created_at"],
            updated_at=workflow["updated_at"],
            duration=calculate_duration(workflow),
            event_count=event_count,
            current_state=current_state,
        )

    except Exception as e:
        if "not found" in str(e).lower():
            raise HTTPException(
                status_code=404, detail=f"Workflow {workflow_id} not found"
            )
        raise HTTPException(status_code=500, detail=f"Failed to get workflow: {str(e)}")


@router.get(
    "/{workflow_id}/events",
    response_model=PaginatedResponse[EventSummary],
    summary="Get workflow events",
    description="""
    Retrieve paginated events for a specific workflow in chronological order.

    **Filtering Options:**
    - `type`: Filter by event type
    - `since`: Filter events after specified timestamp

    **Sorting:**
    - Events are sorted by ID (creation order) by default
    - Use `sort_order=asc` for chronological order, `desc` for reverse

    **Use Cases:**
    - Debug workflow execution flow
    - Audit trail and compliance
    - Understanding state changes over time
    """,
    responses={
        404: {"model": ErrorResponse, "description": "Workflow not found"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
async def get_workflow_events(
    workflow_id: str,
    params: EventListParams = Depends(),
    db: Database = Depends(get_db),
):
    """Get paginated events for a workflow"""
    try:
        # Verify workflow exists
        await db.get_workflow_info(workflow_id)

        # Build WHERE clause
        where_conditions = ["workflow_id = ?"]
        query_params = [workflow_id]

        if params.type:
            where_conditions.append("type = ?")
            query_params.append(params.type.value)

        if params.since:
            where_conditions.append("created_at >= ?")
            query_params.append(params.since.isoformat())

        where_clause = f"WHERE {' AND '.join(where_conditions)}"

        # Get total count
        count_sql = f"SELECT COUNT(*) as total FROM events {where_clause}"
        count_result = await db.fetchone(count_sql, tuple(query_params))
        total = count_result["total"] if count_result else 0

        # Calculate pagination
        pages = math.ceil(total / params.per_page) if total > 0 else 1
        offset = (params.page - 1) * params.per_page

        # Get events for current page
        order_clause = f"ORDER BY {params.sort_by} {params.sort_order.upper()}"
        events_sql = f"""
            SELECT id, workflow_id, type, payload, created_at
            FROM events
            {where_clause}
            {order_clause}
            LIMIT {params.per_page} OFFSET {offset}
        """

        events = await db.query(events_sql, tuple(query_params))

        # Convert to response models
        event_summaries = [
            EventSummary(
                id=e["id"],
                workflow_id=e["workflow_id"],
                type=e["type"],
                payload=json.loads(e["payload"]),
                created_at=e["created_at"],
            )
            for e in events
        ]

        # Build pagination metadata
        meta = PaginationMeta(
            page=params.page,
            per_page=params.per_page,
            total=total,
            pages=pages,
            has_prev=params.page > 1,
            has_next=params.page < pages,
        )

        return PaginatedResponse(data=event_summaries, meta=meta)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get events: {str(e)}")


@router.get(
    "/{workflow_id}/logs",
    response_model=PaginatedResponse[LogEntry],
    summary="Get workflow logs",
    description="""
    Retrieve paginated log entries for a specific workflow.

    **Filtering Options:**
    - `level`: Filter by log level (DEBUG, INFO, WARNING, ERROR)
    - `since`: Filter logs after specified timestamp

    **Use Cases:**
    - Debug workflow execution issues
    - Monitor workflow progress and state changes
    - Troubleshoot failed workflows
    """,
    responses={
        404: {"model": ErrorResponse, "description": "Workflow not found"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
async def get_workflow_logs(
    workflow_id: str, params: LogListParams = Depends(), db: Database = Depends(get_db)
):
    """Get paginated logs for a workflow"""
    try:
        # Verify workflow exists
        workflow_info = await db.get_workflow_info(workflow_id)

        # Build WHERE clause
        where_conditions = ["workflow_id = ?"]
        query_params = [workflow_id]

        if params.level:
            where_conditions.append("level = ?")
            query_params.append(params.level.value)

        if params.since:
            where_conditions.append("created_at >= ?")
            query_params.append(params.since.isoformat())

        where_clause = f"WHERE {' AND '.join(where_conditions)}"

        # Get total count
        count_sql = f"SELECT COUNT(*) as total FROM logs {where_clause}"
        count_result = await db.fetchone(count_sql, tuple(query_params))
        total = count_result["total"] if count_result else 0

        # Calculate pagination
        pages = math.ceil(total / params.per_page) if total > 0 else 1
        offset = (params.page - 1) * params.per_page

        # Get logs for current page
        order_clause = f"ORDER BY {params.sort_by} {params.sort_order.upper()}"
        logs_sql = f"""
            SELECT id, workflow_id, level, message, created_at
            FROM logs
            {where_clause}
            {order_clause}
            LIMIT {params.per_page} OFFSET {offset}
        """

        logs = await db.query(logs_sql, tuple(query_params))

        # Convert to response models
        log_entries = [
            LogEntry(
                id=log["id"],
                workflow_id=log["workflow_id"],
                workflow_name=workflow_info["name"],
                level=log["level"],
                message=log["message"],
                created_at=log["created_at"],
            )
            for log in logs
        ]

        # Build pagination metadata
        meta = PaginationMeta(
            page=params.page,
            per_page=params.per_page,
            total=total,
            pages=pages,
            has_prev=params.page > 1,
            has_next=params.page < pages,
        )

        return PaginatedResponse(data=log_entries, meta=meta)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get logs: {str(e)}")


@router.get(
    "/{workflow_id}/events/stream",
    summary="Stream workflow events (SSE)",
    description="""
    **Server-Sent Events stream for real-time workflow updates.**

    This endpoint provides a persistent connection that streams new events
    as they occur for the specified workflow.

    **Stream Format:**
    ```
    data: {"id": 123, "type": "STEP_START", "payload": {...}, "created_at": "..."}

    data: {"id": 124, "type": "STATE_SET", "payload": {...}, "created_at": "..."}
    ```

    **Usage (JavaScript):**
    ```javascript
    const eventSource = new EventSource('/api/workflows/abc123/events/stream');
    eventSource.onmessage = function(event) {
        const data = JSON.parse(event.data);
        console.log('New event:', data);
    };
    ```

    **Connection Management:**
    - Auto-reconnects on connection loss
    - Streams only new events (no historical replay)
    - Closes automatically when workflow reaches terminal state
    """,
    responses={404: {"model": ErrorResponse, "description": "Workflow not found"}},
)
async def stream_workflow_events(workflow_id: str, db: Database = Depends(get_db)):
    """Stream workflow events via Server-Sent Events"""
    try:
        # Verify workflow exists
        await db.get_workflow_info(workflow_id)

        async def event_stream():
            import asyncio
            import json

            last_event_id = 0

            # Get current max event ID to avoid replaying history
            max_id_sql = "SELECT MAX(id) as max_id FROM events WHERE workflow_id = ?"
            max_result = await db.fetchone(max_id_sql, (workflow_id,))
            if max_result and max_result["max_id"]:
                last_event_id = max_result["max_id"]

            while True:
                try:
                    # Check for new events
                    events_sql = """
                        SELECT id, type, payload, created_at
                        FROM events
                        WHERE workflow_id = ? AND id > ?
                        ORDER BY id ASC
                    """
                    new_events = await db.query(
                        events_sql, (workflow_id, last_event_id)
                    )

                    for event in new_events:
                        event_data = {
                            "id": event["id"],
                            "type": event["type"],
                            "payload": json.loads(event["payload"]),
                            "created_at": event["created_at"],
                        }
                        yield f"data: {json.dumps(event_data)}\n\n"
                        last_event_id = event["id"]

                        # Close stream if workflow is done
                        if event["type"] in [
                            "WORKFLOW_COMPLETED",
                            "WORKFLOW_FAILED",
                            "WORKFLOW_CANCELLED",
                        ]:
                            return

                    # Poll every second
                    await asyncio.sleep(1)

                except Exception as e:
                    yield f"data: {json.dumps({'error': str(e)})}\n\n"
                    return

        return StreamingResponse(
            event_stream(),
            media_type="text/plain",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Content-Type": "text/event-stream",
            },
        )

    except Exception as e:
        if "not found" in str(e).lower():
            raise HTTPException(
                status_code=404, detail=f"Workflow {workflow_id} not found"
            )
        raise HTTPException(
            status_code=500, detail=f"Failed to stream events: {str(e)}"
        )
