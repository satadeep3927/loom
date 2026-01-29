"""Task API Endpoints

Provides REST endpoints for managing and querying workflow tasks.
"""

import math
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from ...database.db import Database
from ..schemas import (
    ErrorResponse,
    PaginatedResponse,
    PaginationMeta,
    TaskDetail,
    TaskKind,
    TaskListParams,
    TaskStatus,
    TaskSummary,
)

router = APIRouter()


async def get_db():
    """Database dependency"""
    async with Database[Any, Any]() as db:
        yield db


@router.get(
    "/",
    response_model=PaginatedResponse[TaskSummary],
    summary="List tasks",
    description="""
    Retrieve a paginated list of tasks with optional filtering and sorting.

    **Filtering Options:**
    - `workflow_id`: Filter by parent workflow ID
    - `status`: Filter by task execution status (PENDING, RUNNING, COMPLETED, FAILED)
    - `kind`: Filter by task type (STEP, ACTIVITY, TIMER)

    **Sorting Options:**
    - `sort_by`: Field to sort by (created_at, updated_at, run_at, attempts)
    - `sort_order`: Sort direction (asc/desc)

    **Pagination:**
    - `page`: Page number (1-based)
    - `per_page`: Items per page (1-1000, default 50)

    **Response includes:**
    - List of task summaries with execution metadata
    - Retry attempt counts and error information
    - Pagination metadata
    """,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid request parameters"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
async def list_tasks(
    params: TaskListParams = Depends(), db: Database = Depends(get_db)
):
    """List tasks with pagination and filtering"""
    try:
        # Build WHERE clause
        where_conditions = []
        query_params = []

        if params.workflow_id:
            where_conditions.append("t.workflow_id = ?")
            query_params.append(params.workflow_id)

        if params.status:
            where_conditions.append("t.status = ?")
            query_params.append(params.status.value)

        if params.kind:
            where_conditions.append("t.kind = ?")
            query_params.append(params.kind.value)

        where_clause = (
            f"WHERE {' AND '.join(where_conditions)}" if where_conditions else ""
        )

        # Get total count
        count_sql = f"""
            SELECT COUNT(*) as total
            FROM tasks t
            JOIN workflows w ON t.workflow_id = w.id
            {where_clause}
        """
        count_result = await db.fetchone(count_sql, tuple(query_params))
        total = count_result["total"] if count_result else 0

        # Calculate pagination
        pages = math.ceil(total / params.per_page) if total > 0 else 1
        offset = (params.page - 1) * params.per_page

        # Build ORDER BY clause
        order_clause = f"ORDER BY t.{params.sort_by} {params.sort_order.upper()}"

        # Get tasks for current page
        tasks_sql = f"""
            SELECT
                t.id,
                t.workflow_id,
                w.name as workflow_name,
                t.kind,
                t.target,
                t.status,
                t.attempts,
                t.max_attempts,
                t.run_at,
                t.created_at,
                t.updated_at,
                t.last_error
            FROM tasks t
            JOIN workflows w ON t.workflow_id = w.id
            {where_clause}
            {order_clause}
            LIMIT {params.per_page} OFFSET {offset}
        """

        tasks = await db.query(tasks_sql, tuple(query_params))

        # Convert to response models
        task_summaries = [
            TaskSummary(
                id=t["id"],
                workflow_id=t["workflow_id"],
                workflow_name=t["workflow_name"],
                kind=TaskKind(t["kind"]),
                target=t["target"],
                status=TaskStatus(t["status"]),
                attempts=t["attempts"],
                max_attempts=t["max_attempts"],
                run_at=t["run_at"],
                created_at=t["created_at"],
                updated_at=t["updated_at"],
                last_error=t["last_error"],
            )
            for t in tasks
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

        return PaginatedResponse(data=task_summaries, meta=meta)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to list tasks: {str(e)}")


@router.get(
    "/{task_id}",
    response_model=TaskDetail,
    summary="Get task details",
    description="""
    Retrieve complete information for a specific task.

    **Returns:**
    - Task execution metadata and current status
    - Retry attempt information and error details
    - Parent workflow information
    - Execution timing and scheduling data

    **Use Cases:**
    - Debug failed or stuck tasks
    - Monitor task retry behavior
    - Understand task execution patterns
    """,
    responses={
        404: {"model": ErrorResponse, "description": "Task not found"},
        500: {"model": ErrorResponse, "description": "Internal server error"},
    },
)
async def get_task(task_id: str, db: Database = Depends(get_db)):
    """Get detailed task information"""
    try:
        # Get task info with workflow name
        task_sql = """
            SELECT
                t.id,
                t.workflow_id,
                w.name as workflow_name,
                t.kind,
                t.target,
                t.status,
                t.attempts,
                t.max_attempts,
                t.run_at,
                t.created_at,
                t.updated_at,
                t.last_error
            FROM tasks t
            JOIN workflows w ON t.workflow_id = w.id
            WHERE t.id = ?
        """

        task = await db.fetchone(task_sql, (task_id,))
        if not task:
            raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

        return TaskDetail(
            id=task["id"],
            workflow_id=task["workflow_id"],
            workflow_name=task["workflow_name"],
            kind=TaskKind(task["kind"]),
            target=task["target"],
            status=TaskStatus(task["status"]),
            attempts=task["attempts"],
            max_attempts=task["max_attempts"],
            run_at=task["run_at"],
            created_at=task["created_at"],
            updated_at=task["updated_at"],
            last_error=task["last_error"],
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get task: {str(e)}")


@router.get(
    "/pending",
    response_model=PaginatedResponse[TaskSummary],
    summary="List pending tasks",
    description="""
    Retrieve tasks that are ready to be executed (status=PENDING, run_at <= now).

    **Optimized endpoint for:**
    - Task queue monitoring
    - Worker load balancing
    - Execution scheduling insights

    **Sorting:**
    - Default sort by `run_at` ascending (oldest first)
    - Shows tasks in execution priority order
    """,
    responses={500: {"model": ErrorResponse, "description": "Internal server error"}},
)
async def list_pending_tasks(
    page: int = 1, per_page: int = 50, db: Database = Depends(get_db)
):
    """List pending tasks ready for execution"""
    try:
        from datetime import datetime

        now = datetime.now().isoformat()

        # Get total count of pending tasks
        count_sql = """
            SELECT COUNT(*) as total
            FROM tasks t
            JOIN workflows w ON t.workflow_id = w.id
            WHERE t.status = 'PENDING' AND t.run_at <= ?
        """
        count_result = await db.fetchone(count_sql, (now,))
        total = count_result["total"] if count_result else 0

        # Calculate pagination
        pages = math.ceil(total / per_page) if total > 0 else 1
        offset = (page - 1) * per_page

        # Get pending tasks ordered by run_at (oldest first)
        tasks_sql = """
            SELECT
                t.id,
                t.workflow_id,
                w.name as workflow_name,
                t.kind,
                t.target,
                t.status,
                t.attempts,
                t.max_attempts,
                t.run_at,
                t.created_at,
                t.updated_at,
                t.last_error
            FROM tasks t
            JOIN workflows w ON t.workflow_id = w.id
            WHERE t.status = 'PENDING' AND t.run_at <= ?
            ORDER BY t.run_at ASC
            LIMIT ? OFFSET ?
        """

        tasks = await db.query(tasks_sql, (now, per_page, offset))

        # Convert to response models
        task_summaries = [
            TaskSummary(
                id=t["id"],
                workflow_id=t["workflow_id"],
                workflow_name=t["workflow_name"],
                kind=TaskKind(t["kind"]),
                target=t["target"],
                status=TaskStatus(t["status"]),
                attempts=t["attempts"],
                max_attempts=t["max_attempts"],
                run_at=t["run_at"],
                created_at=t["created_at"],
                updated_at=t["updated_at"],
                last_error=t["last_error"],
            )
            for t in tasks
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

        return PaginatedResponse(data=task_summaries, meta=meta)

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to list pending tasks: {str(e)}"
        )
