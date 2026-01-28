"""Progress tracking and status display for workflows."""

from datetime import datetime
from typing import Optional

from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskID,
    TextColumn,
    TimeElapsedColumn,
)
from rich.table import Table


class WorkflowProgress:
    """Display workflow execution progress with rich formatting."""

    def __init__(self, workflow_name: str, total_steps: int):
        """Initialize progress tracker.

        Args:
            workflow_name: Name of the workflow being executed
            total_steps: Total number of steps in the workflow
        """
        self.workflow_name = workflow_name
        self.total_steps = total_steps
        self.current_step = 0
        self.started_at = datetime.now()
        self.console = Console()
        self.progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeElapsedColumn(),
            console=self.console,
        )
        self.task_id: Optional[TaskID] = None

    def start(self):
        """Start the progress display."""
        self.task_id = self.progress.add_task(
            f"[cyan]Executing {self.workflow_name}", total=self.total_steps
        )
        self.progress.start()

    def update(self, step_name: str):
        """Update progress to next step.

        Args:
            step_name: Name of the step that just completed
        """
        self.current_step += 1

        if self.task_id is not None:
            self.progress.update(
                self.task_id,
                completed=self.current_step,
                description=f"[cyan]Step: {step_name}",
            )

    def complete(self):
        """Mark the workflow as complete."""
        self.progress.stop()
        elapsed = datetime.now() - self.started_at
        self.console.print(
            f"[green]Workflow '{self.workflow_name}' completed in {elapsed}[/green]"
        )

    def error(self, message: str):
        """Display an error message.

        Args:
            message: Error message to display
        """
        self.progress.stop()
        self.console.print(f"[red]Error: {message}[/red]")


def create_status_table(workflows: list) -> Table:
    """Create a formatted status table for workflows.

    Args:
        workflows: List of workflow dictionaries

    Returns:
        Rich Table object
    """
    table = Table(title="Workflow Status", show_header=True)
    table.add_column("Name", style="cyan", width=30)
    table.add_column("Status", justify="center", width=15)
    table.add_column("Created", style="green", width=20)

    for wf in workflows:
        status_style = {
            "RUNNING": "[yellow]RUNNING[/yellow]",
            "COMPLETED": "[green]COMPLETED[/green]",
            "FAILED": "[red]FAILED[/red]",
            "CANCELED": "[dim]CANCELED[/dim]",
        }.get(wf.get("status", "Unknown"), wf.get("status", "Unknown"))

        table.add_row(
            wf.get("name", "Unknown"), status_style, wf.get("created_at", "Unknown")
        )

    return table
