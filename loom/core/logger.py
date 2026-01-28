import asyncio
import logging
from typing import Any

from ..database.db import Database

# Configure logging with rich formatting if available
try:
    from rich.logging import RichHandler

    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
        handlers=[RichHandler(rich_tracebacks=True, show_time=True, show_path=False)],
    )
except ImportError:
    # Fallback to standard logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )


class WorkflowLogger:
    def __init__(self, ctx: Any):
        self._ctx = ctx
        self._std_logger = logging.getLogger("workflow")
        self._std_logger.setLevel(logging.DEBUG)

    def info(self, msg: str):
        self._log("INFO", msg)

    def error(self, msg: str):
        self._log("ERROR", msg)

    def warning(self, msg: str):
        self._log("WARNING", msg)

    def debug(self, msg: str):
        self._log("DEBUG", msg)

    def _log(self, level: str, msg: str):
        # Only suppress logging if we're actually replaying historical events
        if self._ctx.is_replaying:
            return

        self._std_logger.info(f"[{self._ctx.id[:8]}] {msg}")
        asyncio.create_task(self._write_log_to_db(level, msg))

    async def _write_log_to_db(self, level: str, msg: str):
        # This is a "best effort" write. If it fails, workflow proceeds.
        try:
            async with Database[Any, Any]() as db:
                await db.create_log(
                    workflow_id=self._ctx.id,
                    level=level,
                    message=msg,
                )
        except Exception:
            # Never crash the workflow because logging failed
            pass
