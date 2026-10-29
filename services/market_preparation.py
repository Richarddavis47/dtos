"""Public-safe wording over observed, resident Market preparation state."""

MESSAGES = {
    "waiting": (
        "Market is preparing",
        "Waiting for compatible league and Market evidence. You can keep using Home or My Team while DTOS checks for a ready publication.",
    ),
    "preparing": (
        "Market is preparing",
        "DTOS is preparing Market values for this league. This page will open the Market when compatible values are ready.",
    ),
    "failed": (
        "Market preparation needs another try",
        "The latest preparation did not finish. Try Market again, or return to Home. No missing prices have been replaced with zero.",
    ),
    "source_failed": (
        "League update needed for Market",
        "The last league update did not finish, and no matching Market is ready. Open Home to review your league connection or try Market again. Your saved rankings are unchanged.",
    ),
    "incompatible": (
        "Current Market evidence needs an update",
        "The retained Market does not match this league’s current evidence. Try Market again to request compatible preparation. Saved Custom rankings have not been reset.",
    ),
    "empty": (
        "No Market assets are ready",
        "A prepared publication contains no ranking assets. Try Market again after the league’s next source update. An empty publication is not a complete Market.",
    ),
    "ready": ("Market is ready", "Compatible Market values are ready for this league."),
    "stale": (
        "Last successful Market available",
        "The latest league update failed. You can still use the last compatible Market shown below; its preparation date is shown here.",
    ),
}
STAGES = {
    "waiting": "Waiting for preparation",
    "preparing_generation": "Preparing compatible Market evidence",
    "building": "Preparing Market values",
    "loading_artifact": "Loading prepared Market evidence",
    "publishing": "Publishing prepared Market values",
}


def presentation(snapshot):
    """Explicit allowlist; raw cache diagnostics must never cross this boundary."""
    state = snapshot.get("state") if snapshot.get("state") in MESSAGES else "waiting"
    title, message = MESSAGES[state]
    return dict(
        state=state,
        title=title,
        message=message,
        stage=STAGES.get(snapshot.get("stage"), STAGES["waiting"]),
        updated_at=snapshot.get("updated_at"),
        can_check=bool(snapshot.get("can_check")) and state in {"waiting", "preparing"},
    )


def observe_resident_market(manager, store):
    """No runtime acquisition, pin, touch, provider request, or cache mutation."""
    from src.platform.account_context import current_account

    account = current_account()
    if account is None or account.membership is None:
        return dict(state="waiting", can_check=False)
    league_id = str(account.membership.league_id)
    runtime = manager.resident(league_id)
    if runtime is None or runtime.status in {"closed", "evicting", "failed"}:
        return dict(state="waiting", can_check=False)
    data = runtime.state.get("data") or {}
    if str((data.get("league") or {}).get("league_id") or "") != league_id:
        if runtime.state.get("last_error") and not runtime.state.get("syncing"):
            return dict(state="source_failed", can_check=False)
        return dict(
            state="waiting",
            can_check=runtime.status == "hydrating"
            or bool(runtime.state.get("syncing")),
        )
    context = runtime.canonical_context
    cache = context.market if context else runtime.market_context
    selected_store = context.historical_store if context else store
    if cache is None:
        return dict(state="waiting", can_check=runtime.status == "hydrating")
    result = cache.preparation_status(data, runtime.state, selected_store, league_id)
    if (
        runtime.state.get("data") is not data
        or manager.resident(league_id) is not runtime
    ):
        return dict(state="waiting", can_check=True)
    return result
