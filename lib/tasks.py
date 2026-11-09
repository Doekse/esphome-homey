"""Background work started where it cannot be awaited."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from homey.device import Device

# The event loop keeps only a weak reference to scheduled tasks.
_tasks: set[asyncio.Future[Any]] = set()


def spawn(device: Device, awaitable: Awaitable[Any]) -> None:
    """Run ``awaitable`` in the background and log its error on ``device``."""
    task = asyncio.ensure_future(awaitable)
    _tasks.add(task)

    def done(task: asyncio.Future[Any]) -> None:
        _tasks.discard(task)
        if not task.cancelled() and task.exception() is not None:
            device.error(task.exception())

    task.add_done_callback(done)
