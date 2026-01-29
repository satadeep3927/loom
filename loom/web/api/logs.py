"""Log API Endpoints

Provides REST endpoints for querying workflow logs across the system.
"""

import math
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException

from ...database.db import Database
from ..schemas import (
    ErrorResponse,
    LogEntry,
    LogLevel,
    LogListParams,
    PaginatedResponse,
    PaginationMeta,
)

router = APIRouter()


async def get_db():
    """Database dependency"""
    async with Database[Any, Any]() as db:
        yield db


@router.get(
    "/",
    response_model=PaginatedResponse[LogEntry],
    summary="List logs",
    description="""
    Retrieve a paginated list of log entries across all workflows with optional filtering.

    **Filtering Options:**
    - `workflow_id`: Filter by specific workflow
    - `level`: Filter by log level (DEBUG, INFO, WARNING, ERROR)
    - `since`: Filter logs after specified timestamp

    **Sorting Options:**
    - `sort_by`: Field to sort by (created_at, level)
    - `sort_order`: Sort direction (asc/desc, default desc for recent-first)

    **Pagination:**
    - `page`: Page number (1-based)
    - `per_page`: Items per page (1-1000, default 100)

    **Use Cases:**
    - System-wide log monitoring
    - Error investigation and troubleshooting
    - Workflow execution debugging
    - Log aggregation and analysis
    """,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid request parameters"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
async def list_logs(params: LogListParams = Depends(), db: Database = Depends(get_db)):
    """List logs with pagination and filtering"""
    try:
        # Build WHERE clause
        where_conditions = []
        query_params = []

        if params.workflow_id:
            where_conditions.append("l.workflow_id = ?")
            query_params.append(params.workflow_id)

        if params.level:
            where_conditions.append("l.level = ?")
            query_params.append(params.level.value)

        if params.since:
            where_conditions.append("l.created_at >= ?")
            query_params.append(params.since.isoformat())

        where_clause = (
            f"WHERE {' AND '.join(where_conditions)}" if where_conditions else ""
        )

        # Get total count
        count_sql = f"""
            SELECT COUNT(*) as total
            FROM logs l
            JOIN workflows w ON l.workflow_id = w.id
            {where_clause}
        """
        count_result = await db.fetchone(count_sql, tuple(query_params))
        total = count_result["total"] if count_result else 0

        # Calculate pagination
        pages = math.ceil(total / params.per_page) if total > 0 else 1
        offset = (params.page - 1) * params.per_page

        # Build ORDER BY clause
        order_clause = f"ORDER BY l.{params.sort_by} {params.sort_order.upper()}"

        # Get logs for current page with workflow info
        logs_sql = f"""
            SELECT
                l.id,
                l.workflow_id,
                w.name as workflow_name,
                l.level,
                l.message,
                l.created_at
            FROM logs l
            JOIN workflows w ON l.workflow_id = w.id
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
                workflow_name=log["workflow_name"],
                level=LogLevel(log["level"]),
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

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list logs: {str(e)}")


@router.get(
    "/errors",
    response_model=PaginatedResponse[LogEntry],
    summary="List error logs",
    description="""
    Retrieve error-level log entries across all workflows.

    **Optimized endpoint for:**
    - Error monitoring and alerting
    - Troubleshooting failed workflows
    - System health monitoring

    **Filtering Options:**
    - `workflow_id`: Filter by specific workflow
    - `since`: Filter logs after specified timestamp

    **Sorting:**
    - Default sort by created_at descending (most recent first)
    - Shows critical errors in chronological order
    """,
    responses={500: {"model": ErrorResponse, "description": "Internal server error"}},
)
async def list_error_logs(
    page: int = 1,
    per_page: int = 100,
    workflow_id: Optional[str] = None,
    since: Optional[str] = None,
    db: Database = Depends(get_db),
):
    """List error-level logs"""
    try:
        # Build WHERE clause for ERROR level logs
        where_conditions = ["l.level = 'ERROR'"]
        query_params = []

        if workflow_id:
            where_conditions.append("l.workflow_id = ?")
            query_params.append(workflow_id)

        if since:
            where_conditions.append("l.created_at >= ?")
            query_params.append(since)

        where_clause = f"WHERE {' AND '.join(where_conditions)}"

        # Get total count
        count_sql = f"""
            SELECT COUNT(*) as total
            FROM logs l
            JOIN workflows w ON l.workflow_id = w.id
            {where_clause}
        """
        count_result = await db.fetchone(count_sql, tuple(query_params))
        total = count_result["total"] if count_result else 0

        # Calculate pagination
        pages = math.ceil(total / per_page) if total > 0 else 1
        offset = (page - 1) * per_page

        # Get error logs ordered by created_at desc (newest first)
        logs_sql = f"""
            SELECT
                l.id,
                l.workflow_id,
                w.name as workflow_name,
                l.level,
                l.message,
                l.created_at
            FROM logs l
            JOIN workflows w ON l.workflow_id = w.id
            {where_clause}
            ORDER BY l.created_at DESC
            LIMIT {per_page} OFFSET {offset}
        """

        logs = await db.query(logs_sql, tuple(query_params))

        # Convert to response models
        log_entries = [
            LogEntry(
                id=log["id"],
                workflow_id=log["workflow_id"],
                workflow_name=log["workflow_name"],
                level=LogLevel(log["level"]),
                message=log["message"],
                created_at=log["created_at"],
            )
            for log in logs
        ]

        # Build pagination metadata
        meta = PaginationMeta(
            page=page,
            per_page=per_page,
            total=total,
            pages=pages,
            has_prev=page > 1,
            has_next=page < pages,
        )

        return PaginatedResponse(data=log_entries, meta=meta)

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to list error logs: {str(e)}"
        )


@router.get(
    "/recent",
    response_model=PaginatedResponse[LogEntry],
    summary="List recent logs",
    description="""
    Retrieve the most recent log entries across all workflows.

    **Optimized endpoint for:**
    - Real-time log monitoring
    - Live activity feeds
    - Recent system activity overview

    **Fixed Parameters:**
    - Always sorted by created_at descending (newest first)
    - No filtering (shows all log levels and workflows)
    - Optimized for quick access to latest activity

    **Response:**
    - Shows system-wide recent activity
    - Useful for dashboard "latest activity" sections
    """,
    responses={500: {"model": ErrorResponse, "description": "Internal server error"}},
)
async def list_recent_logs(
    page: int = 1, per_page: int = 50, db: Database = Depends(get_db)
):
    """List recent logs across all workflows"""
    try:
        # Get total count
        count_sql = """
            SELECT COUNT(*) as total
            FROM logs l
            JOIN workflows w ON l.workflow_id = w.id
        """
        count_result = await db.fetchone(count_sql, ())
        total = count_result["total"] if count_result else 0

        # Calculate pagination
        pages = math.ceil(total / per_page) if total > 0 else 1
        offset = (page - 1) * per_page

        # Get recent logs ordered by created_at desc (newest first)
        logs_sql = """
            SELECT
                l.id,
                l.workflow_id,
                w.name as workflow_name,
                l.level,
                l.message,
                l.created_at
            FROM logs l
            JOIN workflows w ON l.workflow_id = w.id
            ORDER BY l.created_at DESC
            LIMIT ? OFFSET ?
        """

        logs = await db.query(logs_sql, (per_page, offset))

        # Convert to response models
        log_entries = [
            LogEntry(
                id=log["id"],
                workflow_id=log["workflow_id"],
                workflow_name=log["workflow_name"],
                level=LogLevel(log["level"]),
                message=log["message"],
                created_at=log["created_at"],
            )
            for log in logs
        ]

        # Build pagination metadata
        meta = PaginationMeta(
            page=page,
            per_page=per_page,
            total=total,
            pages=pages,
            has_prev=page > 1,
            has_next=page < pages,
        )

        return PaginatedResponse(data=log_entries, meta=meta)

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to list recent logs: {str(e)}"
        )
