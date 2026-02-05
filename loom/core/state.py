from contextlib import asynccontextmanager
from inspect import signature
from typing import Any, Callable, Generic

from ..common.errors import StopReplay
from ..schemas.workflow import InputT, StateT


class StateProxy(Generic[InputT, StateT]):
    """Proxy for workflow state management with replay support."""

    _data: StateT
    _ctx: Any
    _batch = None

    def __init__(self, ctx: Any, data: StateT) -> None:
        self._data = data
        self._ctx = ctx

    def __getattr__(self, name: str) -> Any:
        return self._data.get(name)

    def get(self, name: str, default: Any = None) -> Any:
        return self._data.get(name, default)

    def snapshot(self) -> StateT:
        return self._data

    async def set(self, name: str, value: Any) -> None:
        event = self._ctx._peek()
        if event and event["type"] == "STATE_SET" and event["payload"]["key"] == name:
            self._ctx._consume()
            self._data[name] = value
            return

        event = ("STATE_SET", {"key": name, "value": value})

        if self._batch is not None:
            self._batch.append(event)
        else:
            await self._ctx._append_event(*event)
            raise StopReplay

    async def update(self, **updaters: Callable[..., Any]) -> None:
        """Batch update state using updater functions.

        Updater functions can be:
        - Zero-argument: lambda: "new_value"
        - One-argument: lambda old_val: old_val + 1

        Example:
            await ctx.state.update(
                count=lambda c: (c or 0) + 1,
                timestamp=lambda: datetime.now(),
            )
        """
        event = self._ctx._peek()

        if event and event["type"] == "STATE_UPDATE":
            payload = event["payload"]
            if set(payload["values"].keys()) == set(updaters.keys()):
                self._ctx._consume()
                for key, value in payload["values"].items():
                    self._data[key] = value
                return

        new_values = {}
        for key, fn in updaters.items():
            old = self._data.get(key)

            sig = signature(fn)
            if len(sig.parameters) == 0:
                new_values[key] = (
                    fn() if callable(fn) and hasattr(fn, "__call__") else fn
                )
            else:
                new_values[key] = (
                    fn(old) if callable(fn) and hasattr(fn, "__call__") else fn
                )

        event = ("STATE_UPDATE", {"values": new_values})

        if self._batch is not None:
            self._batch.append(event)
        else:
            await self._ctx._append_event(*event)
            raise StopReplay

    @asynccontextmanager
    async def batch(self):
        """Batch multiple state operations into a single transaction.

        Example:
            async with ctx.state.batch():
                await ctx.state.set("a", 1)
                await ctx.state.set("b", 2)
        """
        if self._batch is not None:
            raise RuntimeError("Nested batches are not supported.")

        self._batch = []

        try:
            yield
        finally:
            if self._batch:
                for type, payload in self._batch:
                    await self._ctx._append_event(type, payload)
                self._batch = None
                raise StopReplay
            else:
                self._batch = None
