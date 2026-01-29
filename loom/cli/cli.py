#!/usr/bin/env python3
"""Loom CLI - Command-line interface for Loom workflow orchestration."""

import asyncio
import os  # Added import
import sys
from typing import Any

import click
from rich.console import Console
from rich.table import Table

from ..core.worker import start_worker
from ..database.db import Database

console = Console()


def echo(message: str, **kwargs):
    """Print with rich console."""
    console.print(message)


@click.group()
@click.version_option(version="0.1.0", prog_name="loom")
def cli():
    """Loom - Durable Workflow Orchestration Engine.

    Loom provides event-sourced, deterministic workflow execution with
    automatic recovery and replay capabilities.
    """
    # Ensure current directory is in python path so user modules can be imported
    if os.getcwd() not in sys.path:
        sys.path.insert(0, os.getcwd())
    pass


@cli.command()
@click.option(
    "--workers",
    "-w",
    default=4,
    type=int,
    help="Number of concurrent task workers",
    show_default=True,
)
@click.option(
    "--poll-interval",
    "-p",
    default=0.5,
    type=float,
    help="Polling interval in seconds",
    show_default=True,
)
def worker(workers: int, poll_interval: float):
    """Start a distributed workflow worker.

    The worker continuously polls for available tasks and executes them
    concurrently. Supports graceful shutdown via Ctrl+C or SIGTERM.

    Examples:
        loom worker                    # Start with defaults (4 workers)
        loom worker -w 8               # Start with 8 concurrent workers
        loom worker -w 2 -p 1.0        # 2 workers, 1 second poll interval
    """
    try:
        console.print("[bold green]Starting Loom workflow worker...[/bold green]")
        asyncio.run(start_worker(workers=workers, poll_interval=poll_interval))
    except KeyboardInterrupt:
        pass


@cli.command()
@click.option(
    "--host",
    default="127.0.0.1",
    help="Host to bind to",
    show_default=True,
)
@click.option(
    "--port",
    default=8000,
    type=int,
    help="Port to bind to",
    show_default=True,
)
@click.option(
    "--reload",
    is_flag=True,
    help="Enable auto-reload for development",
)
def web(host: str, port: int, reload: bool):
    """Start the Loom web dashboard.

    Launches a FastAPI-based web interface for monitoring and managing
    workflows, tasks, events, and logs with real-time Server-Sent Events.

    Examples:
        loom web                       # Start on 127.0.0.1:8000
        loom web --host 0.0.0.0        # Bind to all interfaces
        loom web --port 3000           # Use port 3000
        loom web --reload              # Enable auto-reload for development
    """
    try:
        import uvicorn

        console.print("[bold green]Starting Loom web dashboard...[/bold green]")
        console.print(f"[blue]Dashboard: http://{host}:{port}[/blue]")
        console.print(f"[blue]API docs: http://{host}:{port}/docs[/blue]")
        console.print(f"[blue]ReDoc: http://{host}:{port}/redoc[/blue]")

        uvicorn.run(
            "loom.web.main:app",
            host=host,
            port=port,
            reload=reload,
            log_level="info",
            access_log=not reload,  # Reduce noise in dev mode
        )
    except ImportError:
        console.print("[red]FastAPI and uvicorn are required for web dashboard[/red]")
        console.print(
            "[yellow]Install with: pip install 'loom[web]' or pip install fastapi uvicorn[standard][/yellow]"
        )
        sys.exit(1)
    except KeyboardInterrupt:
        console.print("\n[yellow]Web server stopped[/yellow]")


@cli.command()
def init():
    """Initialize the Loom database and migrations.

    Creates the database file and applies all pending migrations.
    Safe to run multiple times - will skip if already initialized.
    """
    echo("Initializing Loom database...")

    async def _init():
        async with Database[Any, Any]() as db:
            await db._init_db()

    try:
        asyncio.run(_init())
        echo("[green]Database initialized successfully[/green]")
    except Exception as e:
        echo(f"[red]Initialization failed: {e}[/red]")
        sys.exit(1)


@cli.command()
@click.option(
    "--limit",
    "-l",
    default=50,
    type=int,
    help="Maximum number of workflows to display",
    show_default=True,
)
@click.option(
    "--status",
    "-s",
    type=click.Choice(
        ["RUNNING", "COMPLETED", "FAILED", "CANCELED"], case_sensitive=False
    ),
    help="Filter by workflow status",
)
def list(limit: int, status: str | None):
    """List workflows with optional filtering.

    Examples:
        loom list                      # List recent workflows
        loom list -l 100               # List up to 100 workflows
        loom list -s RUNNING           # List only running workflows
    """

    async def _list():
        async with Database[Any, Any]() as db:
            if status:
                sql = """
                    SELECT id, name, status, created_at, updated_at
                    FROM workflows
                    WHERE status = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                """
                workflows = await db.query(sql, (status.upper(), limit))
            else:
                sql = """
                    SELECT id, name, status, created_at, updated_at
                    FROM workflows
                    ORDER BY created_at DESC
                    LIMIT ?
                """
                workflows = await db.query(sql, (limit,))

            if not workflows:
                echo("No workflows found")
                return

            table = Table(
                title="Workflows", show_header=True, header_style="bold magenta"
            )
            table.add_column("ID", style="dim", width=40)
            table.add_column("Name", style="cyan", width=25)
            table.add_column("Status", justify="center", width=15)
            table.add_column("Created", style="green", width=20)

            for wf in workflows:
                status_style = {
                    "RUNNING": "[yellow]RUNNING[/yellow]",
                    "COMPLETED": "[green]COMPLETED[/green]",
                    "FAILED": "[red]FAILED[/red]",
                    "CANCELED": "[dim]CANCELED[/dim]",
                }.get(wf["status"], wf["status"])

                table.add_row(wf["id"], wf["name"], status_style, wf["created_at"])

            console.print(table)

    try:
        asyncio.run(_list())
    except Exception as e:
        echo(f"[red]Error: {e}[/red]")
        sys.exit(1)


@cli.command()
@click.argument("workflow_id")
@click.option(
    "--events/--no-events",
    default=False,
    help="Show event history",
)
def inspect(workflow_id: str, events: bool):
    """Inspect detailed workflow information.

    Shows workflow metadata, current state, and optionally event history.

    Examples:
        loom inspect <workflow-id>
        loom inspect <workflow-id> --events
    """

    async def _inspect():
        async with Database[Any, Any]() as db:
            # Get workflow info
            workflow = await db.get_workflow_info(workflow_id)

            echo(f"\n[bold]Workflow: {workflow['name']}[/bold]\n")
            echo(f"ID:          {workflow['id']}")
            echo(f"Status:      {workflow['status']}")
            echo(f"Module:      {workflow['module']}")
            echo(f"Version:     {workflow['version']}")
            echo(f"Created:     {workflow['created_at']}")
            echo(f"Updated:     {workflow['updated_at']}")

            if events:
                event_list = await db.get_workflow_events(workflow_id)
                echo(f"\n[bold]Events ({len(event_list)}):[/bold]\n")

                for i, event in enumerate(event_list, 1):
                    echo(f"{i:3d}. {event['type']}")
                    if event["payload"]:
                        echo(f"     Payload: {event['payload']}")

    try:
        asyncio.run(_inspect())
    except Exception as e:
        echo(f"[red]Error: {e}[/red]")
        sys.exit(1)


@cli.command()
def stats():
    """Show database statistics and health metrics.

    Displays counts of workflows, events, tasks, and logs.
    """

    async def _stats():
        async with Database[Any, Any]() as db:
            workflows = await db.query("SELECT COUNT(*) as count FROM workflows")
            events = await db.query("SELECT COUNT(*) as count FROM events")
            tasks = await db.query("SELECT COUNT(*) as count FROM tasks")
            logs = await db.query("SELECT COUNT(*) as count FROM logs")

            running = await db.query(
                "SELECT COUNT(*) as count FROM workflows WHERE status = 'RUNNING'"
            )

            echo("\n[bold]Database Statistics:[/bold]\n")
            echo(f"Total Workflows:    {list(workflows)[0]['count']}")
            echo(f"Running Workflows:  {list(running)[0]['count']}")
            echo(f"Total Events:       {list(events)[0]['count']}")
            echo(f"Pending Tasks:      {list(tasks)[0]['count']}")
            echo(f"Log Entries:        {list(logs)[0]['count']}")

    try:
        asyncio.run(_stats())
    except Exception as e:
        echo(f"[red]Error: {e}[/red]")
        sys.exit(1)


if __name__ == "__main__":
    cli()
