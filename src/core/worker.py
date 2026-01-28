"""Distributed workflow worker with graceful shutdown and concurrent task execution."""

import asyncio
import signal
import sys
from datetime import datetime, timezone

from .runner import run_once


class WorkflowWorker:
    """Distributed worker for processing workflow tasks with concurrency control.

    Features:
    - Concurrent task processing with configurable worker count
    - Graceful shutdown on SIGINT/SIGTERM
    - Automatic retry on transient failures
    - Configurable polling interval
    - Health monitoring and statistics
    """

    def __init__(
        self,
        workers: int = 4,
        poll_interval: float = 0.5,
        shutdown_timeout: float = 30.0,
    ):
        """Initialize the workflow worker.

        Args:
            workers: Number of concurrent task processors (default: 4)
            poll_interval: Seconds between task queue polls (default: 0.5)
            shutdown_timeout: Max seconds to wait for graceful shutdown (default: 30)
        """
        self.workers = workers
        self.poll_interval = poll_interval
        self.shutdown_timeout = shutdown_timeout
        self._shutdown_event = asyncio.Event()
        self._tasks: set[asyncio.Task] = set()
        self._stats: dict[str, int | datetime | None] = {
            "tasks_completed": 0,
            "tasks_failed": 0,
            "started_at": None,
        }

    async def start(self) -> None:
        """Start the worker and process tasks until shutdown signal."""
        self._stats["started_at"] = datetime.now(timezone.utc)

        # Register signal handlers for graceful shutdown
        self._register_signal_handlers()

        print(f"Workflow worker started with {self.workers} concurrent workers")
        print(f"Polling interval: {self.poll_interval}s")

        try:
            # Start worker tasks
            for i in range(self.workers):
                task = asyncio.create_task(
                    self._worker_loop(worker_id=i), name=f"worker-{i}"
                )
                self._tasks.add(task)

            # Wait for shutdown signal
            await self._shutdown_event.wait()

        finally:
            await self._graceful_shutdown()

    async def _worker_loop(self, worker_id: int) -> None:
        """Main processing loop for a single worker.

        Args:
            worker_id: Unique identifier for this worker instance
        """
        while not self._shutdown_event.is_set():
            try:
                # Try to claim and execute a task
                task_executed = await run_once()

                if task_executed:
                    self._stats["tasks_completed"] = int(self._stats["tasks_completed"]) + 1  # type: ignore
                else:
                    # No tasks available, wait before polling again
                    await asyncio.sleep(self.poll_interval)

            except asyncio.CancelledError:
                # Graceful shutdown requested
                break
            except Exception as e:
                self._stats["tasks_failed"] = int(self._stats["tasks_failed"]) + 1  # type: ignore
                print(f"Worker {worker_id} error: {e}")
                # Brief pause before retrying
                await asyncio.sleep(1.0)

    async def _graceful_shutdown(self) -> None:
        """Gracefully shut down all worker tasks."""
        print("\nShutting down gracefully...")

        # Cancel all worker tasks
        for task in self._tasks:
            task.cancel()

        # Wait for tasks to complete with timeout
        try:
            await asyncio.wait_for(
                asyncio.gather(*self._tasks, return_exceptions=True),
                timeout=self.shutdown_timeout,
            )
        except asyncio.TimeoutError:
            print(f"Shutdown timeout reached ({self.shutdown_timeout}s)")

        self._print_stats()
        print("Worker shutdown complete")

    def _register_signal_handlers(self) -> None:
        """Register handlers for SIGINT and SIGTERM."""

        def signal_handler(sig, frame):
            print(f"\nReceived signal {signal.Signals(sig).name}")
            self._shutdown_event.set()

        # Handle Ctrl+C and termination signals
        signal.signal(signal.SIGINT, signal_handler)
        if sys.platform != "win32":
            signal.signal(signal.SIGTERM, signal_handler)

    def _print_stats(self) -> None:
        """Print worker statistics."""
        started_at = self._stats["started_at"]
        if started_at and isinstance(started_at, datetime):
            uptime = datetime.now(timezone.utc) - started_at
            print("\nWorker Statistics:")
            print(f"   Uptime: {uptime}")
            print(f"   Tasks completed: {self._stats['tasks_completed']}")
            print(f"   Tasks failed: {self._stats['tasks_failed']}")


async def start_worker(workers: int = 4, poll_interval: float = 0.5) -> None:
    """Start a workflow worker process.

    Args:
        workers: Number of concurrent task processors
        poll_interval: Seconds between task queue polls
    """
    worker = WorkflowWorker(workers=workers, poll_interval=poll_interval)
    await worker.start()
