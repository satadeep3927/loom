from contextlib import asynccontextmanager
from typing import Any, Awaitable, Callable, Generic

from ..common.errors import StopReplay
from ..schemas.workflow import InputT, StateT


class StateProxy(Generic[InputT, StateT]):
    """
    Proxy class for managing state interactions.
    Provides methods to get and set state values in the database.
    """

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
            return

        event = ("STATE_SET", {"key": name, "value": value})

        if self._batch is not None:
            self._batch.append(event)
        else:
            await self._ctx._append_event(*event)
            raise StopReplay

    async def update(self, **updaters: Callable[..., Awaitable[Any]]) -> None:
        """
        Example:
            await ctx.state.update(
                count=lambda c: (c or 0) + 1,
                name=lambda _: "Satadeep",
            )
        """
        event = self._ctx._peek()

        if event and event["type"] == "STATE_UPDATE":
            payload = event["payload"]
            if set(payload["values"].keys()) == set(updaters.keys()):
                self._ctx._consume()
                return
        new_values = {}

        for key, fn in updaters.items():
            old = self._data.get(key)
            new_values[key] = await fn(old)

        event = ("STATE_UPDATE", {"values": new_values})

        if self._batch is not None:
            self._batch.append(event)
        else:
            await self._ctx._append_event(*event)
            raise StopReplay

    @asynccontextmanager
    async def batch(self):
        """
        Context manager to batch multiple state updates into a single event.
        Example:
            async with ctx.state.batch():
                await ctx.state.set("a", 1)
                await ctx.state.set("b", 2)
                await ctx.state.update(
                    count=lambda c: (c or 0) + 1,
                )
        """
        if self._batch is not None:
            raise RuntimeError("Nested batches are not supported.")
        self._batch = [] # type: ignore

        try:
            yield
        finally:
            for type, payload in self._batch:
                await self._ctx._append_event(type, payload)
            self._batch = None  # type: ignore
            raise StopReplay
