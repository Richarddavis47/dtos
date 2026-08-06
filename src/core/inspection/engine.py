"""Deterministic, read-only projections of cached DTOS page structure."""
from __future__ import annotations

from typing import Any
from urllib.parse import quote

from app_metadata import VERSION
from src.core.inspection.models import (
    INSPECTION_SCHEMA_VERSION,
    InspectionAction,
    InspectionElement,
    InspectionLink,
    InspectionTable,
    PageInspection,
    PageMetrics,
)
from src.core.team_identity import team_name_for

NAVIGATION = (
    InspectionLink("Asset Market", "/market", "navigation"),
    InspectionLink("Commissioner Desk", "/commissioner", "navigation"),
    InspectionLink("Teams", "/teams", "navigation"),
    InspectionLink("Front Offices", "/front-offices", "navigation"),
    InspectionLink("Trade Intelligence", "/trades", "navigation"),
    InspectionLink("Matchups", "/matchups", "navigation"),
    InspectionLink("Draft Picks", "/picks", "navigation"),
    InspectionLink("Transactions", "/transactions", "navigation"),
    InspectionLink("League History", "/history", "navigation"),
    InspectionLink("League Settings", "/settings", "navigation"),
)


class InspectionEngine:
    """Describe page contracts without rendering HTML or invoking business logic."""

    def __init__(self, state: dict[str, Any]) -> None:
        self._state = state

    @property
    def data(self) -> dict[str, Any]:
        return self._state.get("data") or {}

    def index(self) -> PageInspection:
        pages = self._page_catalog()
        return self._response(
            page_name="AI Inspection System",
            route="/api/inspect",
            sections=(self._element("contract", "Inspection Contract", "section", {
                "read_only": True,
                "cached_state_only": True,
                "business_logic_execution": False,
                "synchronization": False,
            }),),
            cards=tuple(
                self._element(page["key"], page["page_name"], "page", page)
                for page in pages
            ),
            links=tuple(
                InspectionLink(page["page_name"], page["inspection_route"], "inspection")
                for page in pages
            ),
        )

    def pages(self) -> PageInspection:
        pages = self._page_catalog()
        return self._response(
            page_name="Inspectable Pages",
            route="/api/inspect/pages",
            sections=(self._element(
                "page_catalog", "Page Catalog", "section",
                {"count": len(pages)},
            ),),
            tables=(InspectionTable(
                "pages", "DINS Page Registry",
                ("page_name", "page_route", "inspection_route", "scope"),
                tuple(pages),
            ),),
            links=tuple(
                InspectionLink(page["page_name"], page["inspection_route"], "inspection")
                for page in pages
            ),
        )

    def team(self, roster_id: int) -> PageInspection | None:
        team = self._team(roster_id)
        if team is None:
            return None
        players = tuple(team.get("players") or ())
        picks = tuple(team.get("picks_owned") or ())
        player_rows = tuple({
            "player_id": str(player.get("id") or ""),
            "name": player.get("name") or player.get("full_name") or player.get("id"),
            "position": player.get("position"),
            "nfl_team": player.get("team"),
            "roster_slot": player.get("roster_slot"),
            "age": player.get("age"),
        } for player in players)
        pick_rows = tuple({
            "season": pick.get("season"),
            "round": pick.get("round"),
            "original_team": pick.get("original_team") or pick.get("original_roster_id"),
            "acquired": bool(pick.get("is_traded")),
        } for pick in picks)
        empty = []
        if not players:
            empty.append("No cached roster players are available for this team.")
        if not picks:
            empty.append("No cached draft picks are available for this team.")
        links = tuple(
            InspectionLink(
                str(row["name"]),
                f"/players/{quote(row['player_id'], safe='')}",
                "player",
            )
            for row in player_rows
            if row["player_id"]
        )
        placeholders = (
            InspectionAction("compare_teams", "Compare Teams", "/compare", False, True),
            InspectionAction("trade_center", "Trade Center", "/trade-center", False, True),
        )
        return self._response(
            page_name="Team Headquarters",
            route=f"/teams/{roster_id}",
            sections=tuple(
                self._element(key, title, "section", {"source": "cached_state"})
                for key, title in (
                    ("front_office_header", "Front Office Header"),
                    ("asset_snapshot", "Asset Snapshot"),
                    ("front_office_summary", "Front Office Summary"),
                    ("team_grades", "Team Grades"),
                    ("roster", "Roster"),
                    ("draft_capital", "Draft Capital"),
                    ("performance", "Current Team Performance"),
                    ("timeline", "Team Timeline"),
                    ("future_outlook", "Future Outlook"),
                    ("quick_actions", "Quick Actions"),
                )
            ),
            cards=(
                self._element("identity", "Franchise", "card", {
                    "roster_id": roster_id,
                    "team_name": team.get("team_name"),
                    "owner": team.get("owner"),
                    "avatar": team.get("avatar"),
                }),
                self._element("record", "Current Record", "card", {
                    "wins": team.get("wins"),
                    "losses": team.get("losses"),
                    "ties": team.get("ties"),
                }),
                self._element("assets", "Cached Assets", "card", {
                    "player_count": len(players),
                    "draft_pick_count": len(picks),
                    "first_round_pick_count": sum(
                        int(pick.get("round") or 0) == 1 for pick in picks
                    ),
                }),
                self._element("performance", "Cached Performance", "card", {
                    "points_for": team.get("points_for"),
                    "points_against": team.get("points_against"),
                    "max_points": team.get("max_points"),
                }),
            ),
            tables=(
                InspectionTable("roster", "Roster", tuple(player_rows[0]) if player_rows else (
                    "player_id", "name", "position", "nfl_team", "roster_slot", "age"
                ), player_rows, "available" if player_rows else "empty"),
                InspectionTable("draft_capital", "Draft Capital", tuple(pick_rows[0]) if pick_rows else (
                    "season", "round", "original_team", "acquired"
                ), pick_rows, "available" if pick_rows else "empty"),
            ),
            buttons=(
                InspectionAction("transactions", "Transactions", "/transactions", True),
                InspectionAction("league_history", "League History", "/history", True),
                *placeholders,
            ),
            links=links,
            empty_states=tuple(empty),
            placeholder_actions=placeholders,
        )

    def player(self, player_id: str) -> PageInspection | None:
        player, roster_ids = self._player(player_id)
        if player is None:
            return None
        provider_rows = self._provider_values(player_id)
        cards = (
            self._element("identity", "Player Snapshot", "card", {
                "player_id": player_id,
                "name": player.get("full_name") or player.get("name") or player_id,
                "position": player.get("position"),
                "nfl_team": player.get("team"),
                "age": player.get("age"),
                "status": player.get("status"),
                "bye_week": player.get("bye_week"),
            }),
            self._element("ownership", "League Context", "card", {
                "roster_ids": roster_ids,
                "rostered": bool(roster_ids),
                "trending": self._player_trending(player_id),
            }),
            self._element("market", "Live Data and Market", "card", {
                "provider_count": len(provider_rows),
                "source": "cached_market_data",
            }, "available" if provider_rows else "empty"),
        )
        links = tuple(
            InspectionLink(team_name_for(self.data, roster_id), f"/teams/{roster_id}", "team")
            for roster_id in roster_ids
        )
        empty = () if provider_rows else (
            "No cached provider market values are available for this player.",
        )
        return self._response(
            page_name="Player Dossier",
            route=f"/players/{quote(player_id, safe='')}",
            sections=tuple(
                self._element(key, title, "section", {"source": "cached_state"})
                for key, title in (
                    ("executive_summary", "Executive Summary"),
                    ("player_snapshot", "Player Snapshot"),
                    ("live_data_market", "Live Data and Market"),
                    ("core_values", "Four Core Values"),
                    ("strengths", "Strength Analysis"),
                    ("weaknesses", "Weakness Analysis"),
                    ("risk", "Risk Analysis"),
                    ("opportunity", "Opportunity Analysis"),
                    ("team_fit", "Team Fit Analysis"),
                    ("recommendation", "Recommendation"),
                )
            ),
            cards=cards,
            tables=(InspectionTable(
                "provider_values", "Cached Provider Values",
                ("provider", "value", "rank", "updated_at"), provider_rows,
                "available" if provider_rows else "empty",
            ),),
            links=links,
            empty_states=empty,
            warnings=(
                "DINS reports cached evidence only; it does not calculate a new dossier.",
            ),
        )

    def front_office(self, roster_id: int) -> PageInspection | None:
        team = self._team(roster_id)
        if team is None:
            return None
        transactions = self._team_transactions(roster_id)
        return self._response(
            page_name="Front Office Intelligence",
            route=f"/front-offices?front_office={roster_id}",
            sections=tuple(
                self._element(key, title, "section", {"source": "cached_state"})
                for key, title in (
                    ("executive_summary", "Executive Summary"),
                    ("philosophy", "Organizational Philosophy"),
                    ("competitive_window", "Competitive Window"),
                    ("negotiation_style", "Negotiation Style"),
                    ("activity", "Activity Profile"),
                    ("preferences", "Asset Preferences"),
                    ("compatibility", "Trade Compatibility"),
                    ("evidence", "Evidence"),
                )
            ),
            cards=(
                self._element("organization", "Organization", "card", {
                    "roster_id": roster_id,
                    "team_name": team.get("team_name"),
                    "owner": team.get("owner"),
                }),
                self._element("activity", "Cached Activity", "card", {
                    "transaction_count": len(transactions),
                    "player_count": len(team.get("players") or ()),
                    "draft_pick_count": len(team.get("picks_owned") or ()),
                }),
            ),
            tables=(InspectionTable(
                "recent_activity", "Recent Cached Activity",
                ("transaction_id", "type", "status", "created"),
                tuple(transactions[:20]),
                "available" if transactions else "empty",
            ),),
            links=(
                InspectionLink("Team Headquarters", f"/teams/{roster_id}", "team"),
                InspectionLink("Transactions", "/transactions", "transactions"),
            ),
            empty_states=(
                ("No cached transactions involve this Front Office.",)
                if not transactions else ()
            ),
            warnings=(
                "DINS does not execute Front Office Intelligence; it inspects cached inputs and page structure.",
            ),
        )

    def trades(self) -> PageInspection:
        trades = tuple(
            self._transaction_row(row)
            for row in (self.data.get("transactions") or ())
            if str(row.get("type") or "").casefold() == "trade"
        )
        return self._response(
            page_name="Trade Intelligence",
            route="/trades",
            sections=tuple(
                self._element(key, title, "section", {"source": "cached_state"})
                for key, title in (
                    ("opportunities", "Trade Opportunities"),
                    ("partners", "Trade Partner Intelligence"),
                    ("packages", "Trade Packages"),
                    ("impact", "Current and Future Impact"),
                    ("negotiation", "Negotiation Plan"),
                    ("evidence", "Supporting Evidence"),
                )
            ),
            cards=(self._element("trade_count", "Cached Trades", "card", {
                "count": len(trades),
                "source": "cached_transactions",
            }),),
            tables=(InspectionTable(
                "trades", "Cached League Trades",
                ("transaction_id", "type", "status", "created"), trades,
                "available" if trades else "empty",
            ),),
            buttons=(InspectionAction(
                "transactions", "View Transactions", "/transactions?type=trade", True
            ),),
            links=(InspectionLink("Transactions", "/transactions", "transactions"),),
            empty_states=("No cached trades are available.",) if not trades else (),
            warnings=(
                "DINS does not generate or evaluate trade packages.",
            ),
        )

    def _response(
        self,
        *,
        page_name: str,
        route: str,
        sections: tuple[InspectionElement, ...] = (),
        cards: tuple[InspectionElement, ...] = (),
        tables: tuple[InspectionTable, ...] = (),
        charts: tuple[InspectionElement, ...] = (),
        buttons: tuple[InspectionAction, ...] = (),
        links: tuple[InspectionLink, ...] = (),
        empty_states: tuple[str, ...] = (),
        placeholder_actions: tuple[InspectionAction, ...] = (),
        warnings: tuple[str, ...] = (),
    ) -> PageInspection:
        shared_warnings = list(warnings)
        if self._state.get("last_error"):
            shared_warnings.append(f"Cached synchronization warning: {self._state['last_error']}")
        if not self._state.get("last_sync"):
            shared_warnings.append("No successful synchronization timestamp is cached.")
        metrics = PageMetrics(
            len(sections), len(cards), len(tables), len(charts), len(buttons),
            len(NAVIGATION), len(links), len(empty_states),
            len(placeholder_actions), len(shared_warnings),
            sum(len(table.rows) for table in tables),
        )
        return PageInspection(
            VERSION,
            INSPECTION_SCHEMA_VERSION,
            page_name,
            route,
            sections,
            cards,
            tables,
            charts,
            buttons,
            NAVIGATION,
            links,
            empty_states,
            placeholder_actions,
            tuple(shared_warnings),
            metrics,
            self._state.get("last_sync"),
        )

    @staticmethod
    def _element(
        key: str,
        title: str,
        component_type: str,
        data: dict[str, Any],
        status: str = "available",
    ) -> InspectionElement:
        return InspectionElement(key, title, component_type, data, status)

    def _team(self, roster_id: int) -> dict[str, Any] | None:
        return next(
            (
                team for team in (self.data.get("teams") or ())
                if int(team.get("roster_id") or 0) == roster_id
            ),
            None,
        )

    def _player(self, player_id: str) -> tuple[dict[str, Any] | None, tuple[int, ...]]:
        database = self.data.get("players") or {}
        player = database.get(player_id) if isinstance(database, dict) else None
        roster_ids = []
        roster_row = None
        for team in self.data.get("teams") or ():
            for candidate in team.get("players") or ():
                if str(candidate.get("id") or "") == player_id:
                    roster_ids.append(int(team.get("roster_id") or 0))
                    roster_row = roster_row or candidate
        if player is None:
            player = roster_row
        return player, tuple(sorted(set(roster_ids)))

    def _provider_values(self, player_id: str) -> tuple[dict[str, Any], ...]:
        rows = []
        providers = (self.data.get("market_data") or {}).get("providers") or {}
        for provider, values in sorted(providers.items()):
            row = values.get(player_id) if isinstance(values, dict) else None
            if not isinstance(row, dict):
                continue
            rows.append({
                "provider": provider,
                "value": row.get("value"),
                "rank": row.get("rank"),
                "updated_at": row.get("updated_at"),
            })
        return tuple(rows)

    def _player_trending(self, player_id: str) -> dict[str, Any]:
        trending = self.data.get("trending") or {}
        return {
            "adds": next((row.get("count") for row in trending.get("adds") or () if str(row.get("player_id")) == player_id), 0),
            "drops": next((row.get("count") for row in trending.get("drops") or () if str(row.get("player_id")) == player_id), 0),
        }

    def _team_transactions(self, roster_id: int) -> list[dict[str, Any]]:
        rows = []
        for transaction in self.data.get("transactions") or ():
            involved = {int(value) for value in transaction.get("roster_ids") or ()}
            if roster_id in involved:
                rows.append(self._transaction_row(transaction))
        return rows

    @staticmethod
    def _transaction_row(transaction: dict[str, Any]) -> dict[str, Any]:
        return {
            "transaction_id": transaction.get("transaction_id"),
            "type": transaction.get("type"),
            "status": transaction.get("status"),
            "created": transaction.get("created"),
        }

    @staticmethod
    def _page_catalog() -> tuple[dict[str, str], ...]:
        return (
            {"key": "pages", "page_name": "Inspectable Pages", "page_route": "multiple", "inspection_route": "/api/inspect/pages", "scope": "catalog"},
            {"key": "market", "page_name": "Asset Market", "page_route": "/market", "inspection_route": "/api/inspect/market", "scope": "league"},
            {"key": "team", "page_name": "Team Headquarters", "page_route": "/teams/{roster_id}", "inspection_route": "/api/inspect/team/{roster_id}", "scope": "team"},
            {"key": "player", "page_name": "Player Dossier", "page_route": "/players/{player_id}", "inspection_route": "/api/inspect/player/{player_id}", "scope": "player"},
            {"key": "front_office", "page_name": "Front Office Intelligence", "page_route": "/front-offices", "inspection_route": "/api/inspect/front-office/{roster_id}", "scope": "front_office"},
            {"key": "trades", "page_name": "Trade Intelligence", "page_route": "/trades", "inspection_route": "/api/inspect/trades", "scope": "league"},
        )
