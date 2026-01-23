from ..schemas.workflow import Func


def activity(
    name: str | None = None,
    description: str | None = None,
    retry_count: int = 0,
    timeout_seconds: int = 60,
):
    """
    Decorator to define an activity function with execution policies.

    Activities are the only place where side effects should occur in Loom workflows.
    They represent external operations like API calls, database queries, file operations,
    or any non-deterministic work. Activities can be retried on failure and have
    configurable timeouts.

    Args:
        name: Custom name for the activity. If None, uses the function name.
            Should be descriptive and unique for debugging purposes.
        description: Human-readable description of what this activity does.
            Used for documentation, logging, and monitoring.
        retry_count: Number of times to retry the activity on failure.
            Must be >= 0. Set to 0 to disable retries.
        timeout_seconds: Maximum time in seconds to wait for activity completion.
            Must be > 0. Activities exceeding this timeout will be cancelled.

    Returns:
        The decorated function with activity metadata attached.

    Example:
        ```python
        @loom.activity(
            name="send_notification_email",
            description="Send email notification to user",
            retry_count=3,
            timeout_seconds=30
        )
        async def send_email(user_email: str, subject: str, body: str) -> bool:
            # This activity can fail and be retried up to 3 times
            async with httpx.AsyncClient() as client:
                response = await client.post("/api/email/send", json={
                    "to": user_email,
                    "subject": subject,
                    "body": body
                })
                response.raise_for_status()
                return True

        # Usage in workflow step:
        @loom.step
        async def notify_user(self, ctx: WorkflowContext[MyState]):
            success = await ctx.activity(
                send_email,
                ctx.input.user_email,
                "Welcome!",
                "Thanks for joining!"
            )
            ctx.state.email_sent = success
        ```

    Note:
        - Activities should be idempotent when possible (safe to retry)
        - Activities are the execution boundary - no side effects in workflow steps
        - Activity results are persisted and replayed during workflow recovery
        - Long-running activities should implement proper cancellation handling

    Raises:
        ValueError: If retry_count is negative or timeout_seconds is not positive.
    """
    # Validate parameters
    if not isinstance(retry_count, int) or retry_count < 0:
        raise ValueError(
            f"Activity retry_count must be a non-negative integer, got {retry_count}"
        )

    if not isinstance(timeout_seconds, int) or timeout_seconds <= 0:
        raise ValueError(
            f"Activity timeout_seconds must be a positive integer, got {timeout_seconds}"
        )

    if name is not None and not isinstance(name, str):
        raise ValueError(
            f"Activity name must be a string or None, got {type(name).__name__}"
        )

    if description is not None and not isinstance(description, str):
        raise ValueError(
            f"Activity description must be a string or None, got {type(description).__name__}"
        )

    # Reasonable limits to prevent configuration errors
    if retry_count > 100:
        raise ValueError(
            f"Activity retry_count seems excessive: {retry_count}. Maximum recommended is 100."
        )

    if timeout_seconds > 3600:  # 1 hour
        raise ValueError(
            f"Activity timeout_seconds seems excessive: {timeout_seconds}s. "
            f"Consider if this operation should really take more than 1 hour."
        )

    def decorator(func: Func) -> Func:
        """
        Apply activity metadata to the target function.

        Args:
            func: The function to decorate as an activity

        Returns:
            The function with activity metadata attached
        """
        # Attach activity metadata
        setattr(func, "_activity_name", name or getattr(func, "__name__"))
        setattr(func, "_activity_description", description or "")
        setattr(func, "_activity_retry_count", retry_count)
        setattr(func, "_activity_timeout_seconds", timeout_seconds)

        # Add helpful debugging info
        original_name = getattr(func, "__name__", "unknown")
        setattr(func, "_activity_original_name", original_name)

        return func

    return decorator
