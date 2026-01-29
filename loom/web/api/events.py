"""Event API Endpoints

Provides REST endpoints for querying workflow events across the system.
"""

import json
import math
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from ...database.db import Database
from ..schemas import (
    ErrorResponse,
    EventDetail,
    EventListParams,
    EventType,
    PaginatedResponse,
    PaginationMeta,
    WorkflowStatus,
)

router = APIRouter()


async def get_db():
    """Database dependency"""
    async with Database[Any, Any]() as db:
        yield db


@router.get(
    "/",
    response_model=PaginatedResponse[EventDetail],
    summary="List events",
    description="""
    Retrieve a paginated list of events across all workflows with optional filtering.

    **Filtering Options:**
    - `workflow_id`: Filter by specific workflow
    - `type`: Filter by event type (WORKFLOW_STARTED, STEP_START, etc.)
    - `since`: Filter events after specified timestamp

    **Sorting Options:**
    - `sort_by`: Field to sort by (id, created_at)
    - `sort_order`: Sort direction (asc/desc, default desc for recent-first)

    **Pagination:**
    - `page`: Page number (1-based)
    - `per_page`: Items per page (1-1000, default 100)

    **Use Cases:**
    - System-wide event monitoring
    - Debugging cross-workflow issues
    - Audit trail and compliance reporting
    """,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid request parameters"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
async def list_events(
    params: EventListParams = Depends(), db: Database = Depends(get_db)
):
    """List events with pagination and filtering"""
    try:
        # Build WHERE clause
        where_conditions = []
        query_params = []

        if params.workflow_id:
            where_conditions.append("e.workflow_id = ?")
            query_params.append(params.workflow_id)

        if params.type:
            where_conditions.append("e.type = ?")
            query_params.append(params.type.value)

        if params.since:
            where_conditions.append("e.created_at >= ?")
            query_params.append(params.since.isoformat())

        where_clause = (
            f"WHERE {' AND '.join(where_conditions)}" if where_conditions else ""
        )

        # Get total count
        count_sql = f"""
            SELECT COUNT(*) as total
            FROM events e
            JOIN workflows w ON e.workflow_id = w.id
            {where_clause}
        """
        count_result = await db.fetchone(count_sql, tuple(query_params))
        total = count_result["total"] if count_result else 0

        # Calculate pagination
        pages = math.ceil(total / params.per_page) if total > 0 else 1
        offset = (params.page - 1) * params.per_page

        # Build ORDER BY clause
        order_clause = f"ORDER BY e.{params.sort_by} {params.sort_order.upper()}"

        # Get events for current page with workflow info
        events_sql = f"""
            SELECT
                e.id,
                e.workflow_id,
                w.name as workflow_name,
                w.status as workflow_status,
                e.type,
                e.payload,
                e.created_at
            FROM events e
            JOIN workflows w ON e.workflow_id = w.id
            {where_clause}
            {order_clause}
            LIMIT {params.per_page} OFFSET {offset}
        """

        events = await db.query(events_sql, tuple(query_params))

        # Convert to response models
        event_details = [
            EventDetail(
                id=e["id"],
                workflow_id=e["workflow_id"],
                workflow_name=e["workflow_name"],
                workflow_status=WorkflowStatus(e["workflow_status"]),
                type=EventType(e["type"]),
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

        return PaginatedResponse(data=event_details, meta=meta)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list events: {str(e)}")


@router.get(
    "/{event_id}",
    response_model=EventDetail,
    summary="Get event details",
    description="""
    Retrieve complete information for a specific event.

    **Returns:**
    - Complete event data including payload
    - Parent workflow context and status
    - Event timing information

    **Use Cases:**
    - Debug specific event handling
    - Investigate event payload data
    - Understand event context
    """,
    responses={
        404: {"model": ErrorResponse, "description": "Event not found"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
async def get_event(event_id: int, db: Database = Depends(get_db)):
    """Get detailed event information"""
    try:
        # Get event info with workflow context
        event_sql = """
            SELECT
                e.id,
                e.workflow_id,
                w.name as workflow_name,
                w.status as workflow_status,
                e.type,
                e.payload,
                e.created_at
            FROM events e
            JOIN workflows w ON e.workflow_id = w.id
            WHERE e.id = ?
        """

        event = await db.fetchone(event_sql, (event_id,))
        if not event:
            raise HTTPException(status_code=404, detail=f"Event {event_id} not found")

        return EventDetail(
            id=event["id"],
            workflow_id=event["workflow_id"],
            workflow_name=event["workflow_name"],
            workflow_status=WorkflowStatus(event["workflow_status"]),
            type=EventType(event["type"]),
            payload=json.loads(event["payload"]),
            created_at=event["created_at"],
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get event: {str(e)}")


@router.get(
    "/stream",
    summary="Stream all events (SSE)",
    description="""
    **Server-Sent Events stream for real-time system-wide event monitoring.**

    This endpoint provides a persistent connection that streams new events
    as they occur across all workflows in the system.

    **Stream Format:**
    ```
    data: {"id": 123, "workflow_id": "abc", "type": "STEP_START", "payload": {...}}

    data: {"id": 124, "workflow_id": "def", "type": "WORKFLOW_COMPLETED", "payload": {...}}
    ```

    **Usage (JavaScript):**
    ```javascript
    const eventSource = new EventSource('/api/events/stream');
    eventSource.onmessage = function(event) {
        const data = JSON.parse(event.data);
        console.log('System event:', data);
    };
    ```

    **Use Cases:**
    - Real-time system monitoring dashboard
    - Live activity feeds
    - Event-driven UI updates
    - System health monitoring
    """,
    responses={500: {"model": ErrorResponse, "description": "Internal server error"}},
)
async def stream_all_events(db: Database = Depends(get_db)):
    """Stream all system events via Server-Sent Events"""
    try:

        async def event_stream():
            import asyncio
            import json

            last_event_id = 0

            # Get current max event ID to avoid replaying history
            max_id_sql = "SELECT MAX(id) as max_id FROM events"
            max_result = await db.fetchone(max_id_sql, ())
            if max_result and max_result["max_id"]:
                last_event_id = max_result["max_id"]

            while True:
                try:
                    # Check for new events across all workflows
                    events_sql = """
                        SELECT
                            e.id,
                            e.workflow_id,
                            w.name as workflow_name,
                            e.type,
                            e.payload,
                            e.created_at
                        FROM events e
                        JOIN workflows w ON e.workflow_id = w.id
                        WHERE e.id > ?
                        ORDER BY e.id ASC
                        LIMIT 100
                    """
                    new_events = await db.query(events_sql, (last_event_id,))

                    for event in new_events:
                        event_data = {
                            "id": event["id"],
                            "workflow_id": event["workflow_id"],
                            "workflow_name": event["workflow_name"],
                            "type": event["type"],
                            "payload": json.loads(event["payload"]),
                            "created_at": event["created_at"],
                        }
                        yield f"data: {json.dumps(event_data)}\n\n"
                        last_event_id = event["id"]

                    # Poll every second
                    await asyncio.sleep(1)

                except Exception as e:
                    yield f"data: {json.dumps({'error': str(e)})}\n\n"
                    # Don't break on errors, continue polling
                    await asyncio.sleep(5)

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
        raise HTTPException(
            status_code=500, detail=f"Failed to stream events: {str(e)}"
        )
