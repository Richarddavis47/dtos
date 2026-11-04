"""Measured Windows Job memory; unavailable/unbounded jobs never imply capacity."""

from __future__ import annotations
import ctypes
import os


def _api():
    from ctypes import wintypes

    class Basic(ctypes.Structure):
        _fields_ = [
            ("process_time", ctypes.c_longlong),
            ("job_time", ctypes.c_longlong),
            ("flags", wintypes.DWORD),
            ("min_ws", ctypes.c_size_t),
            ("max_ws", ctypes.c_size_t),
            ("active", wintypes.DWORD),
            ("affinity", ctypes.c_size_t),
            ("priority", wintypes.DWORD),
            ("scheduling", wintypes.DWORD),
        ]

    class IO(ctypes.Structure):
        _fields_ = [
            (name, ctypes.c_ulonglong)
            for name in (
                "read_ops",
                "write_ops",
                "other_ops",
                "read_bytes",
                "write_bytes",
                "other_bytes",
            )
        ]

    class Extended(ctypes.Structure):
        _fields_ = [
            ("basic", Basic),
            ("io", IO),
            ("process_limit", ctypes.c_size_t),
            ("job_limit", ctypes.c_size_t),
            ("process_peak", ctypes.c_size_t),
            ("job_peak", ctypes.c_size_t),
        ]

    class Usage(ctypes.Structure):
        _fields_ = [("current", ctypes.c_ulonglong), ("peak", ctypes.c_ulonglong)]

    api = ctypes.WinDLL("kernel32", use_last_error=True)
    api.QueryInformationJobObject.argtypes = [
        wintypes.HANDLE,
        ctypes.c_int,
        ctypes.c_void_p,
        wintypes.DWORD,
        ctypes.c_void_p,
    ]
    api.QueryInformationJobObject.restype = wintypes.BOOL
    return api, Extended, Usage


def measured_job_memory():
    if os.name != "nt":
        return None
    try:
        api, Extended, Usage = _api()
        limits, usage = Extended(), Usage()
        if (
            not api.QueryInformationJobObject(
                None, 9, ctypes.byref(limits), ctypes.sizeof(limits), None
            )
            or not limits.basic.flags & 0x200
            or not limits.job_limit
            or not api.QueryInformationJobObject(
                None, 28, ctypes.byref(usage), ctypes.sizeof(usage), None
            )
        ):
            return None
        return {"current": usage.current, "limit": limits.job_limit, "peak": usage.peak}
    except (OSError, AttributeError):
        return None


def create_validation_job(limit):
    """Enforce an OS budget on the runner and inherited children, never a flag bypass."""
    if os.name != "nt":
        raise RuntimeError("Windows Job validation requires Windows")
    from ctypes import wintypes

    api, Extended, _ = _api()
    api.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
    api.CreateJobObjectW.restype = wintypes.HANDLE
    api.GetCurrentProcess.restype = wintypes.HANDLE
    api.SetInformationJobObject.argtypes = [
        wintypes.HANDLE,
        ctypes.c_int,
        ctypes.c_void_p,
        wintypes.DWORD,
    ]
    api.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    handle = api.CreateJobObjectW(None, None)
    limits = Extended()
    limits.basic.flags = (
        0x200 | 0x2000
    )  # aggregate committed memory; kill children on close
    limits.job_limit = limit
    if (
        not handle
        or not api.SetInformationJobObject(
            handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)
        )
        or not api.AssignProcessToJobObject(handle, api.GetCurrentProcess())
    ):
        raise ctypes.WinError(ctypes.get_last_error())
    # Keep the handle alive until process exit. Closing it would terminate the runner.
    measured = measured_job_memory()
    if not measured or measured["limit"] != limit:
        raise RuntimeError("Cannot verify enforced Windows Job memory accounting")
    return handle, measured
