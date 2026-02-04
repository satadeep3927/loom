"""Loom Web Dashboard FastAPI Application

Main entry point for the web dashboard, providing REST APIs and server-sent events
for monitoring and managing Loom workflows.
"""

import json
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from ..database.db import Database
from .api import events, graphs, logs, stats, tasks, workflows


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup: Initialize database
    async with Database[Any, Any]() as db:
        await db._init_db()
    yield
    # Shutdown: cleanup if needed


app = FastAPI(
    title="Loom Workflow Dashboard",
    description="""
    ## Loom Workflow Orchestration API

    **Loom** is a Python-based durable workflow orchestration engine inspired by Temporal and Durable Task Framework.
    This API provides comprehensive monitoring and management capabilities for workflows, tasks, events, and logs.

    ### Key Features
    - **Event-sourced workflows** with automatic recovery and replay
    - **Deterministic execution** with state reconstruction from events
    - **Real-time monitoring** via Server-Sent Events (SSE)
    - **Comprehensive pagination** and filtering across all endpoints
    - **Task queue management** with retry policies and timeouts

    ### API Structure
    - **Workflows**: Manage workflow lifecycle and state
    - **Tasks**: Monitor task execution and queue status
    - **Events**: Audit trail with real-time streaming
    - **Logs**: Application logging with structured output
    - **Statistics**: System metrics and performance data

    ### Authentication
    Currently no authentication required (development mode).
    Production deployments should implement appropriate security measures.

    ### Real-time Updates
    Use Server-Sent Events endpoints (`/stream/*`) for real-time monitoring.
    These endpoints return `text/event-stream` with JSON payloads.

    ### Rate Limiting
    No rate limiting currently implemented.
    Consider implementing in production environments.
    """,
    version="0.2.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
    contact={
        "name": "Loom Development Team",
        "url": "https://github.com/yourusername/loom",
    },
    license_info={
        "name": "MIT",
        "url": "https://opensource.org/licenses/MIT",
    },
    servers=[
        {"url": "http://localhost:8000", "description": "Development server"},
        {
            "url": "https://your-production-domain.com",
            "description": "Production server",
        },
    ],
    openapi_tags=[
        {
            "name": "Workflows",
            "description": "Manage workflow definitions, execution state, and lifecycle operations.",
        },
        {
            "name": "Tasks",
            "description": "Monitor task execution, queue status, and retry policies.",
        },
        {
            "name": "Events",
            "description": "Event sourcing audit trail with real-time streaming capabilities.",
        },
        {
            "name": "Logs",
            "description": "Application logging with structured output and filtering.",
        },
        {
            "name": "Statistics",
            "description": "System metrics, performance data, and analytics.",
        },
        {
            "name": "Health",
            "description": "System health checks and status monitoring.",
        },
    ],
)

# CORS middleware for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "*",
    ],  # React dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Import and register API routers

app.include_router(workflows.router, prefix="/api/workflows", tags=["Workflows"])
app.include_router(tasks.router, prefix="/api/tasks", tags=["Tasks"])
app.include_router(events.router, prefix="/api/events", tags=["Events"])
app.include_router(logs.router, prefix="/api/logs", tags=["Logs"])
app.include_router(stats.router, prefix="/api/stats", tags=["Statistics"])
app.include_router(graphs.router, prefix="/api/graphs", tags=["Graphs"])

# Mount static files for React UI (must be after API routes)
dist_dir = Path(__file__).parent / "dist"
if dist_dir.exists():
    app.mount("/assets", StaticFiles(directory=str(dist_dir / "assets")), name="assets")


# Health check endpoints
@app.get(
    "/health",
    tags=["Health"],
    summary="Health Check",
    description="Simple health check endpoint to verify API availability.",
    responses={
        200: {
            "description": "API is healthy",
            "content": {
                "application/json": {
                    "example": {
                        "status": "healthy",
                        "timestamp": "2026-01-29T10:30:00Z",
                    }
                }
            },
        }
    },
)
async def health_check():
    """Basic health check endpoint"""
    from datetime import datetime, timezone

    return {"status": "healthy", "timestamp": datetime.now(timezone.utc).isoformat()}


@app.get(
    "/health/detailed",
    tags=["Health"],
    summary="Detailed Health Check",
    description="""
    Comprehensive health check including database connectivity and system status.

    **Checks performed:**
    - Database connection and schema validation
    - Memory usage and performance metrics
    - Active workflow and task counts
    """,
    responses={
        200: {
            "description": "Detailed system health information",
            "content": {
                "application/json": {
                    "example": {
                        "status": "healthy",
                        "timestamp": "2026-01-29T10:30:00Z",
                        "database": {"status": "connected", "response_time_ms": 12},
                        "workflows": {"total": 150, "active": 23},
                        "tasks": {"pending": 5, "running": 2},
                    }
                }
            },
        },
        503: {
            "description": "System unhealthy",
            "content": {
                "application/json": {
                    "example": {
                        "status": "unhealthy",
                        "timestamp": "2026-01-29T10:30:00Z",
                        "errors": ["Database connection failed"],
                    }
                }
            },
        },
    },
)
async def detailed_health_check():
    """Detailed health check with database connectivity"""
    import time
    from datetime import datetime, timezone

    health_status = {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "errors": [],
    }

    try:
        # Check database connectivity
        start_time = time.time()
        async with Database[Any, Any]() as db:
            # Simple query to test database
            result = await db.fetchone("SELECT COUNT(*) as count FROM workflows")
            workflow_count = result["count"] if result else 0

            # Get task counts
            pending_tasks = await db.fetchone(
                "SELECT COUNT(*) as count FROM tasks WHERE status = 'PENDING'"
            )
            running_tasks = await db.fetchone(
                "SELECT COUNT(*) as count FROM tasks WHERE status = 'RUNNING'"
            )

            response_time = (time.time() - start_time) * 1000

            health_status.update(
                {
                    "database": {  # type: ignore
                        "status": "connected",
                        "response_time_ms": round(response_time, 2),
                    },
                    "workflows": {  # type: ignore
                        "total": workflow_count,
                        "active": await _get_active_workflow_count(db),
                    },
                    "tasks": {  # type: ignore
                        "pending": pending_tasks["count"] if pending_tasks else 0,
                        "running": running_tasks["count"] if running_tasks else 0,
                    },
                }
            )

    except Exception as e:
        health_status["status"] = "unhealthy"
        health_status["errors"].append(f"Database connection failed: {str(e)}")  # type: ignore

    status_code = 200 if health_status["status"] == "healthy" else 503
    from fastapi import Response

    return Response(
        content=json.dumps(health_status),
        status_code=status_code,
        media_type="application/json",
    )


async def _get_active_workflow_count(db: Database[Any, Any]) -> int:
    """Get count of active workflows (RUNNING or PENDING)"""
    result = await db.fetchone(
        "SELECT COUNT(*) as count FROM workflows WHERE status IN ('RUNNING', 'PENDING')"
    )
    return result["count"] if result else 0


@app.get("/", include_in_schema=False)
async def root(request: Request):
    """Serve React UI with API URL configuration"""
    dist_dir = Path(__file__).parent / "dist"
    index_file = dist_dir / "index.html"

    # Check if React build exists
    if not index_file.exists():
        return {
            "message": "Loom Dashboard API",
            "docs": "/docs",
            "note": "React UI not built",
        }

    # Read index.html
    with open(index_file, "r", encoding="utf-8") as f:
        html_content = f.read()

    # Inject API URL configuration
    api_url = str(request.base_url).rstrip("/")
    config_script = f"""
    <script>
        window.__API_URL__ = "{api_url}";
    </script>
    """

    # Insert before </head> tag
    html_content = html_content.replace("</head>", f"{config_script}</head>")

    return HTMLResponse(content=html_content)


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "healthy", "service": "loom-dashboard"}
