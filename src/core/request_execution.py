"""Execution boundaries for synchronous manager-read view construction."""
from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import TypeVar


Result = TypeVar("Result")


async def run_manager_read(operation: Callable[[], Result]) -> Result:
    """Run a synchronous manager-read pipeline without blocking request acceptance."""
    return await asyncio.to_thread(operation)
