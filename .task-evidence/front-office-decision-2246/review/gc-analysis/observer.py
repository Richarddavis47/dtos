"""Bounded diagnostic observer; import only in disposable validation runners.

Install after imports and before the existing prelude/target suite. Export after
the runner finishes. No logger, file write, collection, or object enumeration is
performed inside a request. The original callable results/errors are preserved.
"""
from __future__ import annotations

from contextlib import ExitStack
from functools import wraps
import gc
import json
import logging
from pathlib import Path
import sys
import threading
import time
from unittest.mock import patch


class Observer:
    def __init__(self, event_limit: int = 2048, frame_limit: int = 12) -> None:
        # Preallocate tracked containers so recording itself does not allocate a
        # new dict/list/tuple and move an incidental GC threshold into a stage.
        self.rows = [[None] * 9 for _ in range(event_limit)]
        self.frames = [[[None] * 3 for _ in range(frame_limit)]
                       for _ in range(event_limit)]
        self.used = 0
        self.dropped = 0
        self.stack = ExitStack()

    def event(self, kind, name, detail=None, *, capture_frames=False):
        index = self.used
        if index == len(self.rows):
            self.dropped += 1
            return
        self.used = index + 1
        row = self.rows[index]
        row[0] = kind
        row[1] = name
        row[2] = time.time()
        row[3] = time.perf_counter()
        row[4] = time.thread_time()
        row[5] = threading.get_ident()
        row[6] = detail
        if capture_frames:
            frame = sys._getframe(1)
            try:
                count = 0
                while frame is not None and count < len(self.frames[index]):
                    target = self.frames[index][count]
                    target[0] = frame.f_code.co_filename
                    target[1] = frame.f_code.co_name
                    target[2] = frame.f_lineno
                    count += 1
                    frame = frame.f_back
                row[7] = count
            finally:
                del frame

    def gc_event(self, phase, info):
        self.event("gc_" + phase, info["generation"], info.get("collected"),
                   capture_frames=phase == "start")

    def wrap_sync(self, owner, attribute, stage):
        original = getattr(owner, attribute)

        @wraps(original)
        def measured(*args, **kwargs):
            self.event("enter", stage)
            try:
                return original(*args, **kwargs)
            finally:
                self.event("leave", stage)

        self.stack.enter_context(patch.object(owner, attribute, measured))

    def wrap_async(self, owner, attribute, stage):
        original = getattr(owner, attribute)

        @wraps(original)
        async def measured(*args, **kwargs):
            self.event("enter", stage)
            try:
                return await original(*args, **kwargs)
            finally:
                self.event("leave", stage)

        self.stack.enter_context(patch.object(owner, attribute, measured))

    def __enter__(self):
        import fastapi.routing
        import httpx

        gc.callbacks.append(self.gc_event)
        self.stack.callback(gc.callbacks.remove, self.gc_event)
        self.wrap_sync(fastapi.routing, "_extract_endpoint_context", "endpoint_context")
        self.wrap_async(fastapi.routing, "serialize_response", "response_serialization")
        self.wrap_async(httpx.AsyncClient, "get", "client_get")
        self.wrap_async(httpx.ASGITransport, "handle_async_request", "asgi_transport")
        self.wrap_sync(logging.Handler, "handle", "logging_handler")
        return self

    def __exit__(self, *exc):
        return self.stack.__exit__(*exc)

    def export(self, destination):
        events = []
        for index in range(self.used):
            row = self.rows[index]
            event = dict(zip(("kind", "name", "wall_time", "monotonic", "thread_cpu",
                              "thread", "detail", "frame_count", "reserved"), row))
            if row[7]:
                event["frames"] = self.frames[index][:row[7]]
            events.append(event)
        Path(destination).write_text(json.dumps({
            "events": events, "dropped": self.dropped,
            "scope": "Diagnostic stage and GC attribution only; original test assertions unchanged.",
        }, indent=2) + "\n")
