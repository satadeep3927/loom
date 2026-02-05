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

    async def update(self, updater: Callable[..., StateT]) -> None:
        """Update entire state using an updater function.

        The updater can be:
        - Zero-argument: lambda: {"new": "state"}
        - One-argument: lambda old_state: {**old_state, "count": old_state["count"] + 1}

        Example:
            await ctx.state.update(lambda s: {
                **s,
                "count": (s.get("count") or 0) + 1,
                "updated_at": datetime.now()
            })
        """
        event = self._ctx._peek()

        if event and event["type"] == "STATE_UPDATE":
            payload = event["payload"]
            self._ctx._consume()
            self._data = payload["state"]
            return

        sig = signature(updater)
        if len(sig.parameters) == 0:
            new_state = updater()
        else:
            new_state = updater(self._data)

        event = ("STATE_UPDATE", {"state": new_state})

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
