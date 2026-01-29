"""Statistics API Endpoints

Provides REST endpoints for system statistics and metrics.
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from ...database.db import Database
from ..schemas import (
    ErrorResponse,
    SystemStats,
    TaskStats,
    WorkflowStats,
)

router = APIRouter()


async def get_db():
    """Database dependency"""
    async with Database[Any, Any]() as db:
        yield db


@router.get(
    "/",
    response_model=SystemStats,
    summary="Get system statistics",
    description="""
    Retrieve comprehensive system statistics including workflow and task counts.

    **Returns:**
    - **Workflow Statistics**: Total, running, completed, failed, and canceled counts
    - **Task Statistics**: Total, pending, running, completed, and failed counts
    - **Event Count**: Total number of events across all workflows
    - **Log Count**: Total number of log entries across all workflows

    **Use Cases:**
    - System health monitoring dashboard
    - Capacity planning and resource utilization
    - Performance metrics and reporting
    - Overall system status overview
    """,
    responses={500: {"model": ErrorResponse, "description": "Internal server error"}},
)
async def get_system_stats(db: Database = Depends(get_db)):
    """Get comprehensive system statistics"""
    try:
        # Get workflow statistics
        workflow_stats_sql = """
            SELECT
                COUNT(*) as total,
                COUNT(CASE WHEN status = 'RUNNING' THEN 1 END) as running,
                COUNT(CASE WHEN status = 'COMPLETED' THEN 1 END) as completed,
                COUNT(CASE WHEN status = 'FAILED' THEN 1 END) as failed,
                COUNT(CASE WHEN status = 'CANCELED' THEN 1 END) as canceled
            FROM workflows
        """
        workflow_result = await db.fetchone(workflow_stats_sql, ())

        workflow_stats = WorkflowStats(
            total=workflow_result["total"] if workflow_result else 0,
            running=workflow_result["running"] if workflow_result else 0,
            completed=workflow_result["completed"] if workflow_result else 0,
            failed=workflow_result["failed"] if workflow_result else 0,
            canceled=workflow_result["canceled"] if workflow_result else 0,
        )

        # Get task statistics
        task_stats_sql = """
            SELECT
                COUNT(*) as total,
                COUNT(CASE WHEN status = 'PENDING' THEN 1 END) as pending,
                COUNT(CASE WHEN status = 'RUNNING' THEN 1 END) as running,
                COUNT(CASE WHEN status = 'COMPLETED' THEN 1 END) as completed,
                COUNT(CASE WHEN status = 'FAILED' THEN 1 END) as failed
            FROM tasks
        """
        task_result = await db.fetchone(task_stats_sql, ())

        task_stats = TaskStats(
            total=task_result["total"] if task_result else 0,
            pending=task_result["pending"] if task_result else 0,
            running=task_result["running"] if task_result else 0,
            completed=task_result["completed"] if task_result else 0,
            failed=task_result["failed"] if task_result else 0,
        )

        # Get event count
        event_count_sql = "SELECT COUNT(*) as total FROM events"
        event_result = await db.fetchone(event_count_sql, ())

        # Get log count
        log_count_sql = "SELECT COUNT(*) as total FROM logs"
        log_result = await db.fetchone(log_count_sql, ())

        return SystemStats(
            workflows=workflow_stats,
            tasks=task_stats,
            events=event_result["total"] if event_result else 0,
            logs=log_result["total"] if log_result else 0,
        )

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get system stats: {str(e)}"
        )


@router.get(
    "/workflows",
    response_model=WorkflowStats,
    summary="Get workflow statistics",
    description="""
    Retrieve workflow execution statistics by status.

    **Returns:**
    - Total number of workflows
    - Count by status: RUNNING, COMPLETED, FAILED, CANCELED

    **Use Cases:**
    - Workflow success/failure rate monitoring
    - Execution pipeline health checks
    - Performance trend analysis
    """,
    responses={500: {"model": ErrorResponse, "description": "Internal server error"}},
)
async def get_workflow_stats(db: Database = Depends(get_db)):
    """Get workflow statistics"""
    try:
        workflow_stats_sql = """
            SELECT
                COUNT(*) as total,
                COUNT(CASE WHEN status = 'RUNNING' THEN 1 END) as running,
                COUNT(CASE WHEN status = 'COMPLETED' THEN 1 END) as completed,
                COUNT(CASE WHEN status = 'FAILED' THEN 1 END) as failed,
                COUNT(CASE WHEN status = 'CANCELED' THEN 1 END) as canceled
            FROM workflows
        """
        result = await db.fetchone(workflow_stats_sql, ())

        return WorkflowStats(
            total=result["total"] if result else 0,
            running=result["running"] if result else 0,
            completed=result["completed"] if result else 0,
            failed=result["failed"] if result else 0,
            canceled=result["canceled"] if result else 0,
        )

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get workflow stats: {str(e)}"
        )


@router.get(
    "/tasks",
    response_model=TaskStats,
    summary="Get task statistics",
    description="""
    Retrieve task execution statistics by status.

    **Returns:**
    - Total number of tasks
    - Count by status: PENDING, RUNNING, COMPLETED, FAILED

    **Use Cases:**
    - Task queue monitoring and load balancing
    - Worker capacity planning
    - Task execution performance analysis
    """,
    responses={500: {"model": ErrorResponse, "description": "Internal server error"}},
)
async def get_task_stats(db: Database = Depends(get_db)):
    """Get task statistics"""
    try:
        task_stats_sql = """
            SELECT
                COUNT(*) as total,
                COUNT(CASE WHEN status = 'PENDING' THEN 1 END) as pending,
                COUNT(CASE WHEN status = 'RUNNING' THEN 1 END) as running,
                COUNT(CASE WHEN status = 'COMPLETED' THEN 1 END) as completed,
                COUNT(CASE WHEN status = 'FAILED' THEN 1 END) as failed
            FROM tasks
        """
        result = await db.fetchone(task_stats_sql, ())

        return TaskStats(
            total=result["total"] if result else 0,
            pending=result["pending"] if result else 0,
            running=result["running"] if result else 0,
            completed=result["completed"] if result else 0,
            failed=result["failed"] if result else 0,
        )

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get task stats: {str(e)}"
        )


@router.get(
    "/health",
    summary="Get system health indicators",
    description="""
    Retrieve key health indicators for system monitoring.

    **Returns:**
    - Active workflow count (RUNNING status)
    - Pending task count (ready for execution)
    - Recent error count (last hour)
    - System status assessment

    **Health Assessment:**
    - `healthy`: Normal operation (< 10% failed workflows)
    - `degraded`: Some issues (10-25% failed workflows)
    - `unhealthy`: Major issues (> 25% failed workflows)

    **Use Cases:**
    - Health check endpoints for monitoring systems
    - Dashboard status indicators
    - Alerting system integration
    """,
    responses={500: {"model": ErrorResponse, "description": "Internal server error"}},
)
async def get_health_indicators(db: Database = Depends(get_db)):
    """Get system health indicators"""
    try:
        from datetime import datetime, timedelta

        # Get active workflow count
        active_sql = "SELECT COUNT(*) as count FROM workflows WHERE status = 'RUNNING'"
        active_result = await db.fetchone(active_sql, ())
        active_workflows = active_result["count"] if active_result else 0

        # Get pending task count (ready to execute)
        now = datetime.now().isoformat()
        pending_sql = "SELECT COUNT(*) as count FROM tasks WHERE status = 'PENDING' AND run_at <= ?"
        pending_result = await db.fetchone(pending_sql, (now,))
        pending_tasks = pending_result["count"] if pending_result else 0

        # Get recent error count (last hour)
        one_hour_ago = (datetime.now() - timedelta(hours=1)).isoformat()
        error_sql = "SELECT COUNT(*) as count FROM logs WHERE level = 'ERROR' AND created_at >= ?"
        error_result = await db.fetchone(error_sql, (one_hour_ago,))
        recent_errors = error_result["count"] if error_result else 0

        # Calculate system health status
        total_sql = "SELECT COUNT(*) as count FROM workflows"
        failed_sql = "SELECT COUNT(*) as count FROM workflows WHERE status = 'FAILED'"

        total_result = await db.fetchone(total_sql, ())
        failed_result = await db.fetchone(failed_sql, ())

        total_workflows = total_result["count"] if total_result else 0
        failed_workflows = failed_result["count"] if failed_result else 0

        if total_workflows == 0:
            health_status = "healthy"
        else:
            failure_rate = failed_workflows / total_workflows
            if failure_rate <= 0.1:
                health_status = "healthy"
            elif failure_rate <= 0.25:
                health_status = "degraded"
            else:
                health_status = "unhealthy"

        return {
            "status": health_status,
            "active_workflows": active_workflows,
            "pending_tasks": pending_tasks,
            "recent_errors": recent_errors,
            "failure_rate": round(failed_workflows / max(total_workflows, 1) * 100, 2),
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get health indicators: {str(e)}"
        )
