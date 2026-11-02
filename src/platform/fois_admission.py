"""Conservative raw-container admission for optional FOIS work."""

from src.platform.lifecycle import memory_snapshot

# Two times the observed ~243 MiB resident worker, plus a separate 256 MiB
# safety margin. This is admission headroom, not a guaranteed peak bound.
WORKING_RESERVE_BYTES = 512 * 1024 * 1024
SAFETY_MARGIN_BYTES = 256 * 1024 * 1024
SERVICE_LIMIT_BYTES = 2 * 1024 * 1024 * 1024


class FOISMemoryDeferred(RuntimeError):
    """Optional generation was not started; retained grades are not revalidated."""


def require_fois_headroom():
    snapshot = memory_snapshot()
    used, limit = (
        snapshot.get("cgroup_current_bytes"),
        snapshot.get("cgroup_limit_bytes"),
    )
    if (
        type(used) is not int
        or type(limit) is not int
        or used < 0
        or limit <= 0
        or min(limit, SERVICE_LIMIT_BYTES) - used
        < WORKING_RESERVE_BYTES + SAFETY_MARGIN_BYTES
    ):
        raise FOISMemoryDeferred(
            "FOIS preparation deferred to protect league availability. "
            "Retry after other preparation finishes and memory is available. "
            "Previous grades remain RETAINED / NOT REVALIDATED."
        )
