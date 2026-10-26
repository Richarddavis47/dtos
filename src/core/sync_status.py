"""Fixed synchronization status messages; cached exception text is never evidence."""
from __future__ import annotations

from typing import Any, Mapping


def synchronization_warning(state: Mapping[str, Any], *, transactions: bool = False) -> str:
    """Describe availability without reading or formatting an exception message.

    Callers decide whether a failure occurred. Existing last-valid data remains
    usable under its normal admission rules; this message never revalidates it.
    """
    subject = "Transactions" if transactions else "League data"
    if state.get("data"):
        return (f"{subject} could not be refreshed. Showing the last successfully loaded "
                "information; it may be out of date. Try again later.")
    return f"{subject} could not be refreshed. No saved league data is available. Try again or choose another connected league."


def safe_sync_state(state: Mapping[str, Any]) -> dict[str, Any]:
    """Shallow cache/status copy that also handles legacy raw error strings."""
    result = dict(state)
    for key, transactions in (("last_error", False), ("transactions_last_error", True)):
        if key in result:
            result[key] = synchronization_warning(state, transactions=transactions) if result[key] else None
    return result
