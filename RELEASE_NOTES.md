# DTOS v0.9.1 — Transactions Center

DTOS v0.9.1 transforms the current-week transaction feed into a production-ready Front Office Transactions Center while preserving existing routes and raw Sleeper data access.

## Highlights

- Added dashboard metrics for trades, waiver claims, adds, drops, most active team, and most recent transaction.
- Added server-side filters for team, owner, type, player, draft picks, date range, and free-text search.
- Added sortable columns, pagination, responsive tables, player position badges, team links, and player transaction pages.
- Preserved raw Sleeper transaction payload access in expandable details.
- Added a transaction-only refresh action that keeps current filters, reports its last successful sync, and continues serving cached data after a refresh failure.
- Centralized transaction normalization, metrics, filtering, sorting, and pagination in `services/transactions.py`.
- Updated release metadata:
  - Application: DTOS
  - Version: 0.9.1
  - Build: 901
  - Codename: Transactions Center

## Compatibility

- Existing major URLs and the global `/sync` behavior are preserved.
- The Transactions Center uses cached current-week Sleeper data for fast filtering and pagination.
- Player links open transaction-focused DTOS player pages; the broader Player Database remains a future roadmap capability.
