"""Explicit, bounded account preferences; no analytical data or legacy import."""

from datetime import datetime, timezone

STRATEGIES = ("", "WIN NOW", "RETOOL", "REBUILD")
MAX_GOALS = 64


class GoalSaveError(ValueError):
    def __init__(self, code, message, status):
        super().__init__(message)
        self.code, self.status = code, status


def save_goal(store, account, strategy, expected_revision):
    if (
        strategy not in STRATEGIES
        or type(expected_revision) is not int
        or expected_revision < 0
    ):
        raise GoalSaveError(
            "invalid_goal",
            "Choose a supported goal and reload its current save revision.",
            422,
        )
    membership = account.membership
    if not membership or not membership.roster_id:
        raise GoalSaveError(
            "goal_scope_changed",
            "Select your connected league and franchise again.",
            403,
        )
    with store.transaction() as connection:
        timestamp = datetime.now(timezone.utc).isoformat()
        live = connection.execute(
            "SELECT 1 FROM accounts a JOIN account_sessions s USING(account_id) "
            "JOIN account_league_memberships m USING(account_id) "
            "WHERE a.account_id=? AND a.status='active' AND a.active_league_id=? "
            "AND s.session_id=? AND s.revoked_at IS NULL AND s.expires_at>? "
            "AND m.league_id=? AND m.roster_id=? AND m.status='active'",
            (
                account.account_id,
                membership.league_id,
                account.session_id,
                timestamp,
                membership.league_id,
                membership.roster_id,
            ),
        ).fetchone()
        if live is None:
            raise GoalSaveError(
                "goal_scope_changed",
                "Your session or franchise access changed. Sign in and reload.",
                403,
            )
        key = (account.account_id, membership.league_id, membership.roster_id)
        row = connection.execute(
            "SELECT revision FROM account_franchise_goals WHERE account_id=? AND league_id=? AND roster_id=?",
            key,
        ).fetchone()
        revision = int(row["revision"]) if row else 0
        if expected_revision != revision:
            raise GoalSaveError(
                "goal_revision_changed",
                "A newer franchise goal was kept. Reload My Team before saving again.",
                409,
            )
        if (
            row is None
            and connection.execute(
                "SELECT count(*) FROM account_franchise_goals WHERE account_id=?",
                (account.account_id,),
            ).fetchone()[0]
            >= MAX_GOALS
        ):
            raise GoalSaveError(
                "goal_limit",
                "The account has reached its saved goal limit. Existing goals are unchanged.",
                409,
            )
        connection.execute(
            "INSERT INTO account_franchise_goals(account_id,league_id,roster_id,strategy,revision,updated_at) VALUES(?,?,?,?,?,?) "
            "ON CONFLICT(account_id,league_id,roster_id) DO UPDATE SET strategy=excluded.strategy,revision=excluded.revision,updated_at=excluded.updated_at",
            (*key, strategy, revision + 1, timestamp),
        )
    return revision + 1
