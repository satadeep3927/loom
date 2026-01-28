import importlib
import sys
from typing import Any, Awaitable, Callable, cast


def load_activity(module: str, func: str) -> Callable[..., Awaitable[Any]]:

    try:
        activity_module = importlib.import_module(module)

        # Force reload the module to get latest changes
        if module in sys.modules:
            activity_module = importlib.reload(activity_module)

    except ModuleNotFoundError as e:
        raise ModuleNotFoundError(
            f"Cannot import activity module '{module}'. "
            f"Ensure the module exists and is in the Python path."
        ) from e

    try:
        activity_func = getattr(activity_module, func)
    except AttributeError as e:
        raise AttributeError(
            f"Activity function '{func}' not found in module '{module}'. "
            f"Available functions: {[name for name in dir(activity_module) if not name.startswith('_')]}"
        ) from e

    # Validate that it's actually a function
    if not callable(activity_func):
        raise TypeError(
            f"'{func}' from module '{module}' is not callable. "
            f"Got {type(activity_func).__name__}."
        )

    return cast(Callable[..., Awaitable[Any]], activity_func)
